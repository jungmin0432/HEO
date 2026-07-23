from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from heapq import heappop, heappush
from math import inf
from typing import Iterable
from zoneinfo import ZoneInfo


SEOUL_TZ = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class Edge:
    to: str
    minutes: int
    meters: int
    accessible: bool = True


@dataclass(frozen=True)
class Poi:
    id: str
    node: str
    zone: str
    title: str
    detail: str
    kind: str
    purposes: tuple[str, ...]
    dwell_minutes: int
    open_time: str
    close_time: str
    open_weekdays: tuple[int, ...]
    base_score: int
    accessible: bool = True
    status: str = "planned_space"
    status_label: str = "신규 조성 예정"


GATES = {
    "E1-01": {"node": "E1_GATE", "label": "을지로입구 서쪽", "zone": "E1"},
    "E3-01": {"node": "E3_WEST", "label": "을지로3가 서측", "zone": "E3"},
    "E3-02": {"node": "E3_EAST", "label": "을지로3가 동측", "zone": "E3"},
    "E4-01": {"node": "E4_WEST", "label": "을지로4가 서측", "zone": "E4"},
    "E4-02": {"node": "E4_EAST", "label": "을지로4가 동측", "zone": "E4"},
    "DDP-01": {"node": "DDP_GATE", "label": "DDP 연결부", "zone": "DDP"},
}

GATE_ALIASES = {
    "E1": "E1-01",
    "E3": "E3-01",
    "E4": "E4-01",
    "DDP": "DDP-01",
}

DESTINATIONS = {
    "E1": "E1_GATE",
    "E3": "E3_CENTER",
    "E4": "E4_CENTER",
    "DDP": "DDP_GATE",
    "HIPJIRO": "E3_WEST",
    "BANGSAN": "E4_EAST",
}


GRAPH: dict[str, list[Edge]] = {}


def _connect(a: str, b: str, minutes: int, meters: int, accessible: bool = True) -> None:
    GRAPH.setdefault(a, []).append(Edge(b, minutes, meters, accessible))
    GRAPH.setdefault(b, []).append(Edge(a, minutes, meters, accessible))


_connect("E1_GATE", "E1_HALL", 3, 180)
_connect("E1_HALL", "E3_WEST", 6, 410)
_connect("E3_WEST", "E3_CENTER", 4, 250)
_connect("E3_CENTER", "E3_EAST", 4, 260)
_connect("E3_EAST", "E4_WEST", 6, 390)
_connect("E4_WEST", "E4_CENTER", 4, 250)
_connect("E4_CENTER", "E4_EAST", 4, 260)
_connect("E4_EAST", "DDP_GATE", 7, 470)

# 엘리베이터를 이용하는 우회 경로. 시간은 더 들지만 휠체어·유모차 접근 가능.
_connect("E3_WEST", "E3_EAST", 10, 610, accessible=True)
_connect("E4_WEST", "E4_EAST", 10, 620, accessible=True)

# 지하상가는 사실상 일직선 복도다(을지로입구→3가→4가→DDP). 노드의 복도상 순서를
# 매겨두고, 코스 탐색이 한쪽 방향으로만 진행하도록 강제해 같은 구간을 두 번
# 왕복하는 비현실적인 경로를 막는다.
NODE_ORDER = {
    "E1_GATE": 0,
    "E1_HALL": 1,
    "E3_WEST": 2,
    "E3_CENTER": 3,
    "E3_EAST": 4,
    "E4_WEST": 5,
    "E4_CENTER": 6,
    "E4_EAST": 7,
    "DDP_GATE": 8,
}


WEEKDAYS = tuple(range(0, 6))
EVERYDAY = tuple(range(0, 7))

# MVP 시연용 POI 데이터입니다. 실증 전에는 시설공단 점포정보·현장조사값으로 교체합니다.
# 핵심은 각 항목을 어느 노드에 둘지, 실제로 몇 분 머무는지, 지금 영업 중인지를 관리하는 것입니다.
POIS = (
    Poi("e1-panorama", "E1_HALL", "E1", "서울 시간 파노라마", "서울 장면을 고르는 4분 경험", "place", ("look", "memory", "move"), 4, "06:00", "22:00", EVERYDAY, 12),
    Poi("e1-poster", "E1_HALL", "E1", "명함랜드 1호 (사무용품·인쇄물)", "서울 한 장 포스터·명함·인쇄 상담", "shop", ("look", "make"), 6, "10:00", "18:00", WEEKDAYS, 16, status="partner_store", status_label="기존 점포"),
    Poi("e3-archive", "E3_CENTER", "E3", "기억 아카이브 월", "과거·현재 을지로 사진 비교", "place", ("look", "memory", "move"), 6, "06:00", "22:00", EVERYDAY, 14),
    Poi("e3-restore", "E3_CENTER", "E3", "AI 사진복원 스테이션", "개인사진의 복원 전후를 비교", "ai", ("memory",), 6, "10:00", "20:00", EVERYDAY, 19),
    Poi("e3-editor", "E3_CENTER", "E3", "가족 기록 편집 테이블", "사진·문장 선택과 미니 시간책 미리보기", "place", ("look", "memory"), 10, "10:00", "20:00", EVERYDAY, 17),
    Poi("e3-gap-gallery", "E3_CENTER", "E3", "틈새미술관 (전시공간)", "을지로3구역의 전시공간. 전시 관람과 짧은 휴식", "place", ("rest", "look", "memory"), 12, "09:00", "20:00", EVERYDAY, 30, status="existing_facility", status_label="전시공간"),
    Poi("e3-coffee12", "E3_CENTER", "E3", "COFFEE #12 (카페)", "공시 영업시간 06:00~18:00. 음료 구매와 휴식", "shop", ("rest",), 15, "06:00", "18:00", WEEKDAYS, 32, status="partner_store", status_label="기존 점포"),
    Poi("e3-photo", "E3_EAST", "E3", "한독카메라 (카메라·사진)", "사진복원·인화·프레임 상담", "shop", ("memory", "make"), 8, "10:00", "20:00", WEEKDAYS, 21, status="partner_store", status_label="기존 점포"),
    Poi("e4-material", "E4_CENTER", "E4", "제작 재료 라이브러리", "종이·원단·마감 샘플 비교", "place", ("look", "make", "move"), 6, "09:00", "21:00", EVERYDAY, 16),
    Poi("e4-translate", "E4_CENTER", "E4", "AI 제작통역 스테이션", "말·사진을 점포용 제작요청서로 변환", "ai", ("make",), 5, "10:00", "19:00", WEEKDAYS, 24),
    Poi("e4-demo", "E4_CENTER", "E4", "메이커 시연 포켓", "인쇄·마킹·수선 공정을 짧게 관람", "place", ("look", "make"), 8, "10:00", "19:00", WEEKDAYS, 18),
    Poi("e4-atrier", "E4_EAST", "E4", "을지로 아뜨리애 갤러리 (전시공간)", "을지로4가역~DDP 사이의 전시공간. 전시와 휴식", "place", ("rest", "look", "memory"), 12, "09:00", "20:00", EVERYDAY, 31, status="existing_facility", status_label="전시공간"),
    Poi("e4-azit", "E4_EAST", "E4", "Azit Coffee (카페)", "음료 구매와 휴식 후 다음 구간으로 이동", "shop", ("rest",), 15, "09:00", "22:00", EVERYDAY, 30, status="partner_store", status_label="기존 점포"),
    Poi("e4-marking", "E4_EAST", "E4", "현대종합싸인 (사무용품·인쇄물)", "사인·인쇄 제작의 가격·재료·납기 승인", "shop", ("make",), 8, "09:00", "22:00", WEEKDAYS, 25, status="partner_store", status_label="기존 점포"),
    Poi("ddp-wall", "DDP_GATE", "DDP", "도시 시간중첩 월", "훈련원·운동장·DDP의 변화", "place", ("look", "memory", "move"), 5, "06:00", "23:00", EVERYDAY, 15),
    Poi("ddp-showcase", "DDP_GATE", "DDP", "완성품 쇼케이스·픽업", "을지로 점포가 만든 포스터·패치 수령", "place", ("look", "make"), 5, "09:00", "21:00", EVERYDAY, 17),
)

# Competition-demo assumption: all listed stores participate.  Names and
# published hours are sourced from the official directory; indoor route nodes
# are scenario assignments and must be field-verified before live operation.
_POI_OVERRIDES = {
    "e4-marking": {"purposes": ("look", "make")},
}
POIS = tuple(replace(poi, **_POI_OVERRIDES.get(poi.id, {})) for poi in POIS)


def normalize_gate_token(token: str) -> str:
    normalized = (token or "").strip().upper()
    normalized = GATE_ALIASES.get(normalized, normalized)
    if normalized not in GATES:
        raise ValueError(f"알 수 없는 QR 위치코드입니다: {token}")
    return normalized


def parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(SEOUL_TZ)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SEOUL_TZ)
    return parsed.astimezone(SEOUL_TZ)


def _clock_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def is_open(poi: Poi, now: datetime) -> bool:
    if now.weekday() not in poi.open_weekdays:
        return False
    current = now.hour * 60 + now.minute
    opened = _clock_minutes(poi.open_time)
    closed = _clock_minutes(poi.close_time)
    return opened <= current < closed


def shortest_path(start: str, goal: str, accessible_only: bool = False) -> tuple[int, int, list[str]]:
    if start == goal:
        return 0, 0, [start]
    queue: list[tuple[int, int, str, list[str]]] = [(0, 0, start, [start])]
    best: dict[str, int] = {start: 0}
    while queue:
        minutes, meters, node, path = heappop(queue)
        if node == goal:
            return minutes, meters, path
        if minutes > best.get(node, inf):
            continue
        for edge in GRAPH.get(node, []):
            if accessible_only and not edge.accessible:
                continue
            next_minutes = minutes + edge.minutes
            if next_minutes >= best.get(edge.to, inf):
                continue
            best[edge.to] = next_minutes
            heappush(queue, (next_minutes, meters + edge.meters, edge.to, path + [edge.to]))
    raise ValueError("접근 가능한 경로를 찾지 못했습니다.")


def _candidate_score(poi: Poi, purpose: str, start_zone: str) -> float:
    score = poi.base_score
    if purpose in poi.purposes:
        score += 16
    if poi.kind == "shop":
        score += 5
    if purpose == "make" and poi.kind == "ai":
        score += 7
    if poi.zone == start_zone:
        score += 4
    return score


def _route_mix(stops: list[dict]) -> dict[str, int]:
    """Show whether a course connects planned space and existing shops."""
    return {
        "planned_spaces": sum(stop.get("status") == "planned_space" for stop in stops),
        "existing_partner_stores": sum(stop.get("status") == "partner_store" for stop in stops),
    }


def _append_unique_path(existing: list[str], new_path: Iterable[str]) -> list[str]:
    result = list(existing)
    for node in new_path:
        if not result or result[-1] != node:
            result.append(node)
    return result


def recommend_route(
    gate_token: str,
    minutes: int,
    purpose: str,
    destination: str | None = None,
    accessible: bool = False,
    now_value: str | None = None,
    scenario: str = "after_redevelopment",
) -> dict:
    token = normalize_gate_token(gate_token)
    if purpose not in {"look", "memory", "make", "move", "rest"}:
        raise ValueError("purpose는 look, memory, make, move, rest 중 하나여야 합니다.")
    minutes = int(minutes)
    if not 10 <= minutes <= 90:
        raise ValueError("이용 시간은 10~90분 사이여야 합니다.")
    if scenario != "after_redevelopment":
        raise ValueError("현재 MVP는 after_redevelopment(재구성 완료 후) 시나리오만 제공합니다.")

    now = parse_now(now_value)
    gate = GATES[token]
    start_node = gate["node"]
    destination_key = destination.strip().upper() if destination else None
    destination_node = DESTINATIONS.get(destination_key) if destination_key else None
    if destination_key and destination_node is None:
        raise ValueError(f"지원하지 않는 최종 목적지입니다: {destination}")

    purpose_candidates = [poi for poi in POIS if purpose in poi.purposes]
    open_candidates = [poi for poi in purpose_candidates if is_open(poi, now)]
    candidates = [poi for poi in open_candidates if not accessible or poi.accessible]
    max_stops = 2 if minutes <= 15 else 3 if minutes <= 35 else 5

    # 목적지가 정해져 있으면 처음부터 그 방향으로만 걷는다.
    start_direction = 0
    if destination_node:
        delta = NODE_ORDER[destination_node] - NODE_ORDER[start_node]
        if delta != 0:
            start_direction = 1 if delta > 0 else -1

    best_result: dict | None = None

    def consider(
        current_node: str,
        elapsed: int,
        meters: int,
        score: float,
        stops: list[dict],
        path_nodes: list[str],
        visited: frozenset[str],
        direction: int,
    ) -> None:
        nonlocal best_result

        final_elapsed = elapsed
        final_meters = meters
        final_path = list(path_nodes)
        if destination_node:
            end_minutes, end_meters, end_path = shortest_path(current_node, destination_node, accessible)
            final_elapsed += end_minutes
            final_meters += end_meters
            final_path = _append_unique_path(final_path, end_path)

        if final_elapsed <= minutes and (stops or destination_node):
            utilization = final_elapsed / minutes
            final_score = score + utilization * 5 - final_meters / 2000
            mix = _route_mix(stops)
            # A 20+ minute course is stronger when a space experience leads to
            # an existing participating shop.  Short routes and closed shops
            # still receive an honest fallback rather than a forced stop.
            if minutes >= 20 and mix["planned_spaces"] and mix["existing_partner_stores"]:
                final_score += 55
            if destination_node:
                final_score += 8
            if best_result is None or final_score > best_result["score"]:
                best_result = {
                    "score": round(final_score, 2),
                    "elapsed": final_elapsed,
                    "meters": final_meters,
                    "stops": list(stops),
                    "path_nodes": final_path,
                }

        if len(stops) >= max_stops:
            return

        current_pos = NODE_ORDER[current_node]
        ranked = sorted(
            (poi for poi in candidates if poi.id not in visited),
            key=lambda poi: _candidate_score(poi, purpose, gate["zone"]),
            reverse=True,
        )
        for poi in ranked:
            poi_pos = NODE_ORDER[poi.node]
            # 이미 한쪽 방향으로 걷기 시작했다면, 지나온 구간을 되짚어가는
            # 후보는 건너뛴다 (같은 복도 왕복 방지).
            if direction > 0 and poi_pos < current_pos:
                continue
            if direction < 0 and poi_pos > current_pos:
                continue

            walk_minutes, walk_meters, walk_path = shortest_path(current_node, poi.node, accessible)
            next_elapsed = elapsed + walk_minutes + poi.dwell_minutes
            if next_elapsed > minutes:
                continue
            if destination_node:
                reserve_minutes, _, _ = shortest_path(poi.node, destination_node, accessible)
                if next_elapsed + reserve_minutes > minutes:
                    continue

            arrival = elapsed + walk_minutes
            stop = {
                "id": poi.id,
                "title": poi.title,
                "detail": poi.detail,
                "kind": poi.kind,
                "status": poi.status,
                "status_label": poi.status_label,
                "zone": poi.zone,
                "arrival_minute": arrival,
                "leave_minute": next_elapsed,
                "walk_minutes_from_previous": walk_minutes,
                "dwell_minutes": poi.dwell_minutes,
            }
            next_direction = direction
            if next_direction == 0 and poi_pos != current_pos:
                next_direction = 1 if poi_pos > current_pos else -1
            consider(
                poi.node,
                next_elapsed,
                meters + walk_meters,
                score + _candidate_score(poi, purpose, gate["zone"]),
                stops + [stop],
                _append_unique_path(path_nodes, walk_path),
                visited | {poi.id},
                next_direction,
            )

    consider(start_node, 0, 0, 0, [], [start_node], frozenset(), start_direction)

    if best_result is None:
        return {
            "gate": {"token": token, **gate},
            "route": None,
            "message": "선택한 시간과 영업조건에서 이용 가능한 코스가 없습니다.",
            "filters": {
                "purpose_candidates": len(purpose_candidates),
                "closed_removed": len(purpose_candidates) - len(open_candidates),
                "accessibility_removed": len(open_candidates) - len(candidates),
            },
        }

    # 이동·체험으로 채우지 못한 시간도 숨기지 않는다. 이용자가 10분을 선택했다면
    # 화면의 총 일정은 정확히 10분이어야 하므로, 남는 시간은 다음 이동 준비·상품 비교 등
    # 안전한 완충시간으로 명시한다. 이 값은 실제 점포의 제작시간을 임의로 늘리지 않는다.
    active_minutes = best_result["elapsed"]
    # Leave genuinely unused time visible to the visitor; do not fabricate it as travel.
    buffer_minutes = max(0, minutes - active_minutes)
    timed_stops = list(best_result["stops"])

    return {
        "gate": {"token": token, **gate},
        "request": {
            "minutes": minutes,
            "purpose": purpose,
            "destination": destination_key,
            "accessible": accessible,
            "scenario": scenario,
            "calculated_at": now.isoformat(),
        },
        "route": {
            # total_minutes는 사용자가 선택한 시간과 항상 동일하다.
            "total_minutes": minutes,
            "active_minutes": active_minutes,
            "buffer_minutes": 0,
            "walking_distance_m": best_result["meters"],
            "remaining_minutes": buffer_minutes,
            "stops": timed_stops,
            "path_nodes": best_result["path_nodes"],
            "destination_node": destination_node,
            "mix": _route_mix(best_result["stops"]),
        },
        "filters": {
            "purpose_candidates": len(purpose_candidates),
            "closed_removed": len(purpose_candidates) - len(open_candidates),
            "accessibility_removed": len(open_candidates) - len(candidates),
        },
        "engine": {
            "name": "QR constrained route recommender",
            "method": "영업·시간·접근성 필터 + Dijkstra 최단거리 + 제한시간 내 조합 탐색",
            "version": "1.0.0",
        },
        "scenario_notice": "신규 조성 예정 공간과 기존 참여점포를 함께 반영한 완성 후 시뮬레이션입니다. 점포별 실제 참여·영업상태는 개장 전 확정 데이터로 갱신해야 합니다.",
    }


def gate_information(gate_token: str) -> dict:
    token = normalize_gate_token(gate_token)
    return {"token": token, **GATES[token]}
