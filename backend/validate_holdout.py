"""Held-out validation run against the criteria pre-registered in VALIDATION_DESIGN.md.

This script must not be edited to change scenario composition after results are
seen -- the scenarios below match VALIDATION_DESIGN.md exactly (72 time-stability
cases + 24 accessibility cases), none of which overlap the exploratory scenarios
already reported in benchmark_results.md.

Run: python validate_holdout.py
Writes: validation_results.md
"""

from __future__ import annotations

import json
from pathlib import Path

from route_engine import GATES, recommend_route
from benchmark_baseline import greedy_route, mix_quality

TIME_STABILITY_TIMESTAMPS = [
    ("평일 오전", "2026-07-23T10:30:00+09:00"),   # Thursday
    ("평일 저녁", "2026-07-23T21:00:00+09:00"),   # Thursday
    ("토요일 오후", "2026-07-25T14:00:00+09:00"),  # Saturday
    ("일요일 오후", "2026-07-26T14:00:00+09:00"),  # Sunday -- WEEKDAYS-only shops closed
]
PURPOSES = ["look", "make", "rest"]
GATE_TOKENS = list(GATES.keys())
MINUTES_FOR_TIME_SET = 30
MINUTES_FOR_ACCESS_SET = [10, 30, 60, 90]


def run_current(gate, minutes, purpose, accessible=False, now_value=None):
    result = recommend_route(gate, minutes, purpose, accessible=accessible, now_value=now_value)
    route = result.get("route")
    if not route:
        return None
    return {
        "active_minutes": route["active_minutes"],
        "walking_distance_m": route["walking_distance_m"],
        "stop_count": len(route["stops"]),
        "mix": route["mix"],
    }


def run_greedy(gate, minutes, purpose, accessible=False, now_value=None):
    return greedy_route(gate, minutes, purpose, accessible=accessible, now_value=now_value)


def time_stability_set():
    rows = []
    for label, ts in TIME_STABILITY_TIMESTAMPS:
        for gate in GATE_TOKENS:
            for purpose in PURPOSES:
                c = run_current(gate, MINUTES_FOR_TIME_SET, purpose, now_value=ts)
                g = run_greedy(gate, MINUTES_FOR_TIME_SET, purpose, now_value=ts)
                rows.append({"slot": label, "now": ts, "gate": gate, "purpose": purpose,
                             "current": c, "greedy": g})
    return rows


def accessibility_set():
    rows = []
    now = "2026-07-23T14:00:00+09:00"  # Thursday afternoon, most shops open
    for gate in GATE_TOKENS:
        for minutes in MINUTES_FOR_ACCESS_SET:
            c = run_current(gate, minutes, "look", accessible=True, now_value=now)
            g = run_greedy(gate, minutes, "look", accessible=True, now_value=now)
            rows.append({"gate": gate, "minutes": minutes, "current": c, "greedy": g})
    return rows


def pct(n, d):
    return round(100 * n / d, 1) if d else 0.0


def main():
    ts_rows = time_stability_set()
    acc_rows = accessibility_set()

    # --- Criterion A: time utilization advantage (current vs greedy), across all held-out cases ---
    all_paired = [(r["current"], r["greedy"], r.get("minutes", MINUTES_FOR_TIME_SET)) for r in ts_rows]
    all_paired += [(r["current"], r["greedy"], r["minutes"]) for r in acc_rows]
    util_c = [c["active_minutes"] / m for c, g, m in all_paired if c]
    util_g = [g["active_minutes"] / m for c, g, m in all_paired if g]
    avg_util_c = pct(sum(util_c), len(util_c)) if util_c else 0.0
    avg_util_g = pct(sum(util_g), len(util_g)) if util_g else 0.0
    criterion_a_gap = round(avg_util_c - avg_util_g, 1)
    criterion_a_pass = criterion_a_gap >= 10.0

    # --- Criterion B: mix-quality advantage, time-stability set only (no destination) ---
    mix_c = [mix_quality(r["current"]["mix"]) for r in ts_rows if r["current"]]
    mix_g = [mix_quality(r["greedy"]["mix"]) for r in ts_rows if r["greedy"]]
    mix_rate_c = pct(sum(mix_c), len(mix_c)) if mix_c else 0.0
    mix_rate_g = pct(sum(mix_g), len(mix_g)) if mix_g else 0.0
    criterion_b_gap = round(mix_rate_c - mix_rate_g, 1)
    criterion_b_pass = criterion_b_gap >= 5.0

    # --- Criterion C: walking-distance guard rail ---
    dist_c = [c["walking_distance_m"] / c["stop_count"] for c, g, m in all_paired if c and c["stop_count"]]
    dist_g = [g["walking_distance_m"] / g["stop_count"] for c, g, m in all_paired if g and g["stop_count"]]
    avg_dist_c = round(sum(dist_c) / len(dist_c), 1) if dist_c else 0.0
    avg_dist_g = round(sum(dist_g) / len(dist_g), 1) if dist_g else 0.0
    dist_increase_pct = round(100 * (avg_dist_c - avg_dist_g) / avg_dist_g, 1) if avg_dist_g else 0.0
    criterion_c_pass = dist_increase_pct <= 100.0

    # --- Criterion D: per-timeslot success rate >= 90% for the current engine ---
    slot_success = {}
    for label, _ in TIME_STABILITY_TIMESTAMPS:
        slot_cases = [r for r in ts_rows if r["slot"] == label]
        ok = [r for r in slot_cases if r["current"]]
        slot_success[label] = pct(len(ok), len(slot_cases))
    criterion_d_pass = all(v >= 90.0 for v in slot_success.values())

    # --- Criterion E: accessible=True success rate >= 80% for the current engine ---
    acc_ok = [r for r in acc_rows if r["current"]]
    criterion_e_rate = pct(len(acc_ok), len(acc_rows))
    criterion_e_pass = criterion_e_rate >= 80.0

    overall_pass = criterion_a_pass and criterion_b_pass and criterion_d_pass and criterion_e_pass

    lines = []
    lines.append("# Held-out 검증 결과\n")
    lines.append("`VALIDATION_DESIGN.md`에 사전 등록한 기준(A-E)을 새로운 96개 시나리오(기존 벤치마크와 겹치지 않음)에 적용한 결과.\n")
    lines.append("| 기준 | 판정 | 실측값 | 기준값 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| A. 시간 활용도 우위 | {'PASS' if criterion_a_pass else 'FAIL'} | 현재 {avg_util_c}% vs 그리디 {avg_util_g}% (차이 {criterion_a_gap}%p) | +10%p 이상 |")
    lines.append(f"| B. 거래 연결(혼합달성) 우위 | {'PASS' if criterion_b_pass else 'FAIL'} | 현재 {mix_rate_c}% vs 그리디 {mix_rate_g}% (차이 {criterion_b_gap}%p) | +5%p 이상 |")
    lines.append(f"| C. 보행 부담 가드레일 | {'PASS' if criterion_c_pass else 'FAIL'} | 정류장당 도보거리 현재 {avg_dist_c}m vs 그리디 {avg_dist_g}m (증가 {dist_increase_pct}%) | 증가 100% 이내 |")
    lines.append(f"| D. 시간대 안정성 (성공률≥90%) | {'PASS' if criterion_d_pass else 'FAIL'} | {json.dumps(slot_success, ensure_ascii=False)} | 각 시간대 90% 이상 |")
    lines.append(f"| E. 접근성 최소 기준 (성공률≥80%) | {'PASS' if criterion_e_pass else 'FAIL'} | {criterion_e_rate}% | 80% 이상 |")
    lines.append("")
    lines.append(f"## 종합 판정: {'검증 통과' if overall_pass else '검증 미통과'}")
    lines.append("(A·B·D·E 모두 통과해야 종합 통과. C는 가드레일이며 실패 시에도 종합판정을 무효화하지 않고 한계로 기록.)\n")

    report = "\n".join(lines)
    Path("validation_results.md").write_text(report, encoding="utf-8")
    Path("validation_results.json").write_text(json.dumps({
        "criterion_a": {"pass": criterion_a_pass, "current_pct": avg_util_c, "greedy_pct": avg_util_g, "gap_pp": criterion_a_gap},
        "criterion_b": {"pass": criterion_b_pass, "current_pct": mix_rate_c, "greedy_pct": mix_rate_g, "gap_pp": criterion_b_gap},
        "criterion_c": {"pass": criterion_c_pass, "current_m": avg_dist_c, "greedy_m": avg_dist_g, "increase_pct": dist_increase_pct},
        "criterion_d": {"pass": criterion_d_pass, "per_slot": slot_success},
        "criterion_e": {"pass": criterion_e_pass, "success_rate_pct": criterion_e_rate},
        "overall_pass": overall_pass,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
