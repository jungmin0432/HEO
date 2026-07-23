"""AI가 직접 코스(어떤 장소를, 어떤 순서로)를 설계하는 파이프라인.

기존 recommend_route()는 사람이 만든 점수식(_candidate_score)이 어떤 장소를
넣을지 정한다. 이 모듈은 그 대신 LLM(무료 Groq)이 사용자의 자유문장과 실제
매장 데이터를 보고 코스 자체를 제안하게 한다.

LLM은 창작(어떤 조합이 사용자 의도에 맞는가)만 담당하고, 시간예산·영업시간·
존재하지 않는 매장 여부는 전부 이 모듈의 결정적 검증기가 재계산해서 확인한다.
LLM 응답이 검증을 통과하지 못하면 위반 항목을 제거해 복구하거나, 그래도 남는
것이 없으면 기존 recommend_route()로 폴백한다 — AI가 조용히 사실을 지어내는
결과가 사용자에게 나가는 일은 없다.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from route_engine import (
    GATES,
    POIS,
    DESTINATIONS,
    is_open,
    normalize_gate_token,
    parse_now,
    shortest_path,
    recommend_route,
    _route_mix,
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("EULJIRO_GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

_DB_PATH = Path(__file__).resolve().parent / "data" / "euljiro_route_20260722_project.db"


def _real_store_names() -> list[str]:
    """161 real underground-mall stores from the official directory. None of
    them have a field-verified position yet (location_status is unverified
    for all rows), so they cannot enter the walkable route math — they are
    passed to the LLM only as grounding context, never as a stop_id source."""
    if not _DB_PATH.exists():
        return []
    try:
        con = sqlite3.connect(str(_DB_PATH))
        try:
            cur = con.execute("SELECT store_name FROM stores ORDER BY store_id")
            return [row[0] for row in cur.fetchall()]
        finally:
            con.close()
    except sqlite3.Error:
        return []


REAL_STORE_NAMES = _real_store_names()


class AIDesignerUnavailable(RuntimeError):
    pass


_ZONE_ROTATION = ("E1", "E3", "E4", "DDP")
_ZONE_NODE = {"E1": "E1_HALL", "E3": "E3_CENTER", "E4": "E4_CENTER", "DDP": "DDP_GATE"}
_REST_KEYWORDS = ("카페", "커피", "COFFEE", "다방", "Coffee")


def _unverified_store_pois() -> list[dict]:
    """The 161 real store names have no field-verified position (see
    _real_store_names' docstring). We still want the AI to have real-world
    inventory to reason over, so each name is assigned to one of the 4 known
    corridor zones by simple round-robin — an explicitly disclosed placement
    assumption, not a verified fact. location_verified=False travels with
    every one of these entries so nothing downstream can present it as
    confirmed. Never used to assert "this store is physically at X"."""
    out = []
    for i, name in enumerate(REAL_STORE_NAMES):
        zone = _ZONE_ROTATION[i % len(_ZONE_ROTATION)]
        purpose = ("rest",) if any(k in name for k in _REST_KEYWORDS) else ("look", "make")
        out.append({
            "id": f"real-{i:03d}",
            "title": name,
            "detail": "서울시설공단 을지로 지하도상가 공식 입점 상호 (실명, 위치는 미검증 가정)",
            "kind": "shop",
            "purposes": purpose,
            "zone": zone,
            "node": _ZONE_NODE[zone],
            "dwell_minutes": 8,
            "status": "partner_store",
            "status_label": "기존 점포",
            "location_verified": False,
        })
    return out


def _candidate_payload(gate_token: str, minutes: int, accessible: bool, now_value: str | None) -> list[dict]:
    token = normalize_gate_token(gate_token)
    gate = GATES[token]
    now = parse_now(now_value)
    items = []
    for poi in POIS:
        if not is_open(poi, now):
            continue
        if accessible and not poi.accessible:
            continue
        walk_minutes, walk_meters, _ = shortest_path(gate["node"], poi.node, accessible)
        if walk_minutes + poi.dwell_minutes > minutes:
            continue
        items.append({
            "id": poi.id,
            "title": poi.title,
            "detail": poi.detail,
            "kind": poi.kind,
            "purposes": list(poi.purposes),
            "zone": poi.zone,
            "node": poi.node,
            "status": poi.status,
            "status_label": poi.status_label,
            "dwell_minutes": poi.dwell_minutes,
            "walk_minutes_from_gate": walk_minutes,
            "walk_meters_from_gate": walk_meters,
            "location_verified": True,
        })

    # Free-tier Groq TPM limits (8000 tokens/request) cap how many candidates
    # a single call can carry. 161 real names alone already exceed that, so
    # only a bounded, disclosed sample rides along each request rather than
    # silently truncating with no explanation.
    UNVERIFIED_CAP = 40
    for entry in _unverified_store_pois()[:UNVERIFIED_CAP]:
        walk_minutes, walk_meters, _ = shortest_path(gate["node"], entry["node"], accessible)
        if walk_minutes + entry["dwell_minutes"] > minutes:
            continue
        items.append({
            "id": entry["id"],
            "title": entry["title"],
            "detail": entry["detail"],
            "kind": entry["kind"],
            "purposes": list(entry["purposes"]),
            "zone": entry["zone"],
            "node": entry["node"],
            "status": entry["status"],
            "status_label": entry["status_label"],
            "dwell_minutes": entry["dwell_minutes"],
            "walk_minutes_from_gate": walk_minutes,
            "walk_meters_from_gate": walk_meters,
            "location_verified": False,
        })
    return items


def _build_prompt(gate_label: str, minutes: int, text: str, candidates: list[dict]) -> tuple[str, str]:
    system = (
        "You design a short walking course inside the Euljiro underground shopping "
        "corridor in Seoul. You may ONLY choose stops from the \"candidates\" list "
        "by their exact \"id\" field — never invent a place, name, or id that is "
        "not in that list. Order the chosen stops as the visitor should walk them. "
        "Return ONLY compact JSON: "
        "{\"stop_ids\": [\"id1\", \"id2\", ...], \"reason\": \"one short Korean sentence\"}. "
        "Pick as many or as few stops as genuinely fit the visitor's request — an "
        "empty list is a valid answer if nothing fits. Each candidate has \"v\": "
        "true (field-confirmed position) or false (real store name, but its "
        "position is an even-distribution placement assumption, not confirmed). "
        "Prefer verified candidates when they fit equally well; unverified ones "
        "are still real businesses and fine to include, just do not claim their "
        "position is confirmed in your reason. Budget check before you answer: "
        "\"walk_min\" is the walk time from the GATE to that single candidate, "
        "NOT between two candidates — walking between two stops normally costs "
        "similar or more time than either one's walk_min alone. Add up each "
        "chosen stop's dwell_min plus a realistic walk estimate between "
        "consecutive stops; the running total must stay at or under "
        "time_budget_minutes. When unsure, choose fewer stops rather than more "
        "— a short correct course beats a long one that runs over budget."
    )
    compact = [
        {
            "id": c["id"], "title": c["title"], "kind": c["kind"],
            "purposes": c["purposes"], "zone": c["zone"],
            "dwell_min": c["dwell_minutes"], "walk_min": c["walk_minutes_from_gate"],
            "v": c["location_verified"],
        }
        for c in candidates
    ]
    user = json.dumps({
        "gate": gate_label,
        "time_budget_minutes": minutes,
        "visitor_request": text,
        "candidates": compact,
    }, ensure_ascii=False, separators=(",", ":"))
    return system, user


def _call_groq(system: str, user: str, model: str | None = None) -> dict:
    if not GROQ_API_KEY:
        raise AIDesignerUnavailable("GROQ_API_KEY is not configured")
    model = model or GROQ_MODEL
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    if "gpt-oss" in model:
        body["reasoning_effort"] = "low"
    request = urllib.request.Request(
        GROQ_BASE_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; EuljiroRouteAI/1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise AIDesignerUnavailable(f"Groq request failed: {error.code} {message[:200]}") from error
    except urllib.error.URLError as error:
        raise AIDesignerUnavailable(f"Groq network error: {error.reason}") from error

    content = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise AIDesignerUnavailable("Groq did not return valid JSON")
        parsed = json.loads(match.group(0))
    parsed["_usage"] = usage
    return parsed


def _validate_and_build(
    stop_ids: list[str],
    candidates: list[dict],
    gate_token: str,
    minutes: int,
    destination: str | None,
    accessible: bool,
) -> dict:
    """Re-derive real timing/meters from the graph. Drop anything that doesn't
    check out instead of trusting the LLM's own numbers."""
    token = normalize_gate_token(gate_token)
    gate = GATES[token]
    by_id = {c["id"]: c for c in candidates}

    destination_node = DESTINATIONS.get(destination.strip().upper()) if destination else None

    kept_ids = [sid for sid in dict.fromkeys(stop_ids) if sid in by_id]
    dropped_hallucinated = [sid for sid in stop_ids if sid not in by_id]

    current_node = gate["node"]
    elapsed = 0
    meters = 0
    stops = []
    dropped_over_budget = []
    path_nodes = [current_node]

    for sid in kept_ids:
        c = by_id[sid]
        walk_minutes, walk_meters, walk_path = shortest_path(current_node, c["node"], accessible)
        next_elapsed = elapsed + walk_minutes + c["dwell_minutes"]
        if destination_node:
            reserve_minutes, _, _ = shortest_path(c["node"], destination_node, accessible)
            if next_elapsed + reserve_minutes > minutes:
                dropped_over_budget.append(sid)
                continue
        if next_elapsed > minutes:
            dropped_over_budget.append(sid)
            continue
        arrival = elapsed + walk_minutes
        stops.append({
            "id": c["id"], "title": c["title"], "detail": c["detail"], "kind": c["kind"],
            "status": c["status"], "status_label": c["status_label"], "zone": c["zone"],
            "arrival_minute": arrival, "leave_minute": next_elapsed,
            "walk_minutes_from_previous": walk_minutes, "dwell_minutes": c["dwell_minutes"],
            "location_verified": c["location_verified"],
        })
        for node in walk_path:
            if not path_nodes or path_nodes[-1] != node:
                path_nodes.append(node)
        current_node = c["node"]
        elapsed = next_elapsed
        meters += walk_meters

    final_elapsed = elapsed
    final_meters = meters
    if destination_node:
        end_minutes, end_meters, end_path = shortest_path(current_node, destination_node, accessible)
        final_elapsed += end_minutes
        final_meters += end_meters
        for node in end_path:
            if not path_nodes or path_nodes[-1] != node:
                path_nodes.append(node)

    return {
        "total_minutes": minutes,
        "active_minutes": final_elapsed,
        "buffer_minutes": 0,
        "walking_distance_m": final_meters,
        "remaining_minutes": max(0, minutes - final_elapsed),
        "stops": stops,
        "path_nodes": path_nodes,
        "destination_node": destination_node,
        "mix": _route_mix(stops),
        "validator": {
            "requested_stop_ids": stop_ids,
            "dropped_hallucinated": dropped_hallucinated,
            "dropped_over_budget": dropped_over_budget,
            "kept": len(stops),
        },
    }


def design_course(
    gate_token: str,
    minutes: int,
    purpose: str,
    destination: str | None,
    accessible: bool,
    text: str,
    now_value: str | None = None,
    model: str | None = None,
) -> dict:
    """Returns a dict shaped like recommend_route()'s output, plus an "engine" field."""
    token = normalize_gate_token(gate_token)
    gate = GATES[token]
    candidates = _candidate_payload(gate_token, minutes, accessible, now_value)

    if not candidates:
        fallback = recommend_route(gate_token, minutes, purpose, destination, accessible, now_value)
        fallback["engine"] = "heuristic_fallback"
        fallback["engine_reason"] = "영업 중인 후보가 없어 AI 설계를 건너뜀"
        return fallback

    system, user = _build_prompt(gate["label"], minutes, text, candidates)
    try:
        raw = _call_groq(system, user, model=model)
    except AIDesignerUnavailable as error:
        fallback = recommend_route(gate_token, minutes, purpose, destination, accessible, now_value)
        fallback["engine"] = "heuristic_fallback"
        fallback["engine_reason"] = str(error)
        return fallback

    stop_ids = raw.get("stop_ids") or []
    built = _validate_and_build(stop_ids, candidates, gate_token, minutes, destination, accessible)

    if not built["stops"]:
        fallback = recommend_route(gate_token, minutes, purpose, destination, accessible, now_value)
        fallback["engine"] = "heuristic_fallback"
        fallback["engine_reason"] = "AI가 고른 장소가 전부 검증에서 탈락해 기존 알고리즘으로 대체"
        fallback["validator"] = built["validator"]
        fallback["llm_model"] = model or GROQ_MODEL
        return fallback

    return {
        "gate": {"token": token, **gate},
        "route": built,
        "engine": "ai_designer",
        "engine_reason": raw.get("reason", ""),
        "llm_usage": raw.get("_usage", {}),
        "llm_model": model or GROQ_MODEL,
    }
