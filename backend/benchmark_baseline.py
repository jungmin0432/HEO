"""Baseline comparison for the route recommender.

Compares two selection strategies that share the exact same data
(gates, POIs, walking-time graph, opening hours) and only differ in
how the next stop is chosen:

* greedy_route   -- naive baseline: always walk to the nearest open,
                    purpose-matching, unvisited candidate. This is what
                    a plain "list nearby open shops" or generic map app
                    effectively does -- no lookahead, no scoring.
* recommend_route -- the shipped engine: exhaustively searches stop
                    combinations within the time budget and keeps the
                    highest-scoring one (purpose fit, mix of planned
                    space + existing shop, time utilization, walking
                    cost).

Run: python benchmark_baseline.py
Writes: benchmark_results.md (per-scenario table + aggregate summary)
"""

from __future__ import annotations

import json
from pathlib import Path

from route_engine import (
    GATES,
    POIS,
    DESTINATIONS,
    normalize_gate_token,
    parse_now,
    is_open,
    shortest_path,
    recommend_route,
    _route_mix,
    _append_unique_path,
)

NOW = "2026-07-21T15:00:00+09:00"  # Tuesday 15:00 -- same fixture used by test_route_engine.py


def greedy_route(gate_token, minutes, purpose, destination=None, accessible=False, now_value=None):
    """Naive nearest-open-candidate baseline. Reuses the exact same graph,
    POI data, and opening-hours rule as the shipped engine -- only the
    selection strategy (nearest vs. best-scoring combination) differs.
    """
    token = normalize_gate_token(gate_token)
    now = parse_now(now_value)
    gate = GATES[token]
    start_node = gate["node"]
    destination_key = destination.strip().upper() if destination else None
    destination_node = DESTINATIONS.get(destination_key) if destination_key else None

    candidates = [
        poi for poi in POIS
        if purpose in poi.purposes and is_open(poi, now) and (not accessible or poi.accessible)
    ]
    max_stops = 2 if minutes <= 15 else 3 if minutes <= 35 else 5

    current = start_node
    elapsed = 0
    meters = 0
    stops = []
    visited = set()
    path_nodes = [start_node]

    while len(stops) < max_stops:
        best = None
        best_walk = None
        best_meta = None
        for poi in candidates:
            if poi.id in visited:
                continue
            walk_minutes, walk_meters, walk_path = shortest_path(current, poi.node, accessible)
            next_elapsed = elapsed + walk_minutes + poi.dwell_minutes
            if next_elapsed > minutes:
                continue
            if destination_node:
                reserve_minutes, _, _ = shortest_path(poi.node, destination_node, accessible)
                if next_elapsed + reserve_minutes > minutes:
                    continue
            if best is None or walk_minutes < best_walk:
                best = poi
                best_walk = walk_minutes
                best_meta = (walk_meters, walk_path)
        if best is None:
            break
        walk_meters, walk_path = best_meta
        arrival = elapsed + best_walk
        leave = arrival + best.dwell_minutes
        stops.append({
            "id": best.id,
            "title": best.title,
            "status": best.status,
            "zone": best.zone,
            "arrival_minute": arrival,
            "leave_minute": leave,
            "walk_minutes_from_previous": best_walk,
            "dwell_minutes": best.dwell_minutes,
        })
        elapsed = leave
        meters += walk_meters
        current = best.node
        visited.add(best.id)
        path_nodes = _append_unique_path(path_nodes, walk_path)

    if destination_node:
        d_minutes, d_meters, d_path = shortest_path(current, destination_node, accessible)
        if elapsed + d_minutes <= minutes:
            elapsed += d_minutes
            meters += d_meters
            path_nodes = _append_unique_path(path_nodes, d_path)

    if not stops and not destination_node:
        return None

    return {
        "gate": token,
        "stops": stops,
        "active_minutes": elapsed,
        "remaining_minutes": max(0, minutes - elapsed),
        "walking_distance_m": meters,
        "mix": _route_mix(stops),
        "stop_count": len(stops),
    }


def run_current(gate_token, minutes, purpose, destination=None):
    result = recommend_route(gate_token, minutes, purpose, destination=destination, now_value=NOW)
    route = result.get("route")
    if not route:
        return None
    return {
        "gate": result["gate"]["token"],
        "stops": route["stops"],
        "active_minutes": route["active_minutes"],
        "remaining_minutes": route["remaining_minutes"],
        "walking_distance_m": route["walking_distance_m"],
        "mix": route["mix"],
        "stop_count": len(route["stops"]),
    }


def mix_quality(mix: dict) -> int:
    return 1 if mix.get("planned_spaces", 0) > 0 and mix.get("existing_partner_stores", 0) > 0 else 0


def summarize(rows: list[dict], label: str) -> dict:
    ok = [r for r in rows if r["result"] is not None]
    n = len(rows)
    if not ok:
        return {"label": label, "n": n, "success_rate": 0.0}
    util = [r["result"]["active_minutes"] / r["minutes"] for r in ok]
    dist = [r["result"]["walking_distance_m"] for r in ok]
    stops = [r["result"]["stop_count"] for r in ok]
    dist_per_stop = [d / s for d, s in zip(dist, stops) if s]
    mixq = [mix_quality(r["result"]["mix"]) for r in ok]
    return {
        "label": label,
        "n": n,
        "success_rate": round(100 * len(ok) / n, 1),
        "avg_utilization_pct": round(100 * sum(util) / len(util), 1),
        "avg_stops": round(sum(stops) / len(stops), 2),
        "avg_distance_m": round(sum(dist) / len(dist), 1),
        "avg_distance_per_stop_m": round(sum(dist_per_stop) / len(dist_per_stop), 1) if dist_per_stop else None,
        "mix_quality_rate_pct": round(100 * sum(mixq) / len(mixq), 1),
    }


def main():
    gates = list(GATES.keys())
    minutes_options = [10, 30, 60, 90]
    purposes = ["look", "memory", "make", "move", "rest"]

    greedy_rows, current_rows = [], []

    for gate in gates:
        for minutes in minutes_options:
            for purpose in purposes:
                g = greedy_route(gate, minutes, purpose, now_value=NOW)
                c = run_current(gate, minutes, purpose)
                greedy_rows.append({"gate": gate, "minutes": minutes, "purpose": purpose, "result": g})
                current_rows.append({"gate": gate, "minutes": minutes, "purpose": purpose, "result": c})

    # secondary matrix: destination-constrained (60-minute budget, all gates, all destinations)
    dest_greedy, dest_current = [], []
    for gate in gates:
        for dest in ["DDP", "HIPJIRO", "BANGSAN"]:
            g = greedy_route(gate, 60, "look", destination=dest, now_value=NOW)
            c = run_current(gate, 60, "look", destination=dest)
            dest_greedy.append({"gate": gate, "minutes": 60, "purpose": "look+dest", "result": g})
            dest_current.append({"gate": gate, "minutes": 60, "purpose": "look+dest", "result": c})

    summary_greedy = summarize(greedy_rows, "그리디 최근접 (baseline)")
    summary_current = summarize(current_rows, "현재 엔진 (Dijkstra + 조합탐색)")
    summary_greedy_dest = summarize(dest_greedy, "그리디 최근접 + 목적지 지정")
    summary_current_dest = summarize(dest_current, "현재 엔진 + 목적지 지정")

    lines = []
    lines.append("# 경로 추천 알고리즘 베이스라인 비교\n")
    lines.append(f"고정 시각: `{NOW}` (평일 15:00) · 시나리오 {len(greedy_rows)}건 (게이트 {len(gates)} x 시간 {len(minutes_options)} x 목적 {len(purposes)})\n")
    lines.append("## 전체 탐색 시나리오 (목적지 미지정)\n")
    lines.append("| 지표 | 그리디 최근접 (baseline) | 현재 엔진 |")
    lines.append("|---|---|---|")
    lines.append(f"| 성공률 (코스 산출 성공) | {summary_greedy['success_rate']}% | {summary_current['success_rate']}% |")
    lines.append(f"| 평균 시간활용률 (active/total) | {summary_greedy['avg_utilization_pct']}% | {summary_current['avg_utilization_pct']}% |")
    lines.append(f"| 평균 정류장 수 | {summary_greedy['avg_stops']} | {summary_current['avg_stops']} |")
    lines.append(f"| 평균 총 도보거리 (m) | {summary_greedy['avg_distance_m']} | {summary_current['avg_distance_m']} |")
    lines.append(f"| 정류장당 평균 도보거리 (m) | {summary_greedy['avg_distance_per_stop_m']} | {summary_current['avg_distance_per_stop_m']} |")
    lines.append(f"| 신규공간+기존점포 혼합 달성률 | {summary_greedy['mix_quality_rate_pct']}% | {summary_current['mix_quality_rate_pct']}% |")
    lines.append("")
    lines.append("## 목적지 지정 시나리오 (60분 고정, DDP/힙지로/방산 목적지)\n")
    lines.append("| 지표 | 그리디 최근접 | 현재 엔진 |")
    lines.append("|---|---|---|")
    lines.append(f"| 성공률 | {summary_greedy_dest['success_rate']}% | {summary_current_dest['success_rate']}% |")
    lines.append(f"| 평균 시간활용률 | {summary_greedy_dest['avg_utilization_pct']}% | {summary_current_dest['avg_utilization_pct']}% |")
    lines.append(f"| 평균 정류장 수 | {summary_greedy_dest['avg_stops']} | {summary_current_dest['avg_stops']} |")
    lines.append(f"| 평균 총 도보거리 (m) | {summary_greedy_dest['avg_distance_m']} | {summary_current_dest['avg_distance_m']} |")
    lines.append(f"| 혼합 달성률 | {summary_greedy_dest['mix_quality_rate_pct']}% | {summary_current_dest['mix_quality_rate_pct']}% |")
    lines.append("")

    report = "\n".join(lines)
    Path("benchmark_results.md").write_text(report, encoding="utf-8")

    detail = {
        "now": NOW,
        "full_matrix": {"greedy": summary_greedy, "current": summary_current},
        "destination_matrix": {"greedy": summary_greedy_dest, "current": summary_current_dest},
    }
    Path("benchmark_results.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
