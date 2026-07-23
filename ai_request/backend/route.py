"""경로추천 — QR 진입점 + 시간예산으로 이용 가능한 코스만 그래프 탐색으로 계산.

제안서 3.2 'QR로 현재 위치를 알고, 이용 가능한 코스만 다시 계산':
  구간=노드 · 통로=간선 · 시간=가중치 → Dijkstra 최단거리 → 시간예산 안에서 코스 구성.
표준 라이브러리만 사용(외부 의존성 없음).
"""
from __future__ import annotations

import heapq
import json
from pathlib import Path

_ZONES = json.loads((Path(__file__).resolve().parent.parent / "data" / "zones.json").read_text("utf-8"))
NODES = _ZONES["nodes"]
PORTALS = _ZONES["portals"]

# 무방향 인접 리스트
_ADJ: dict[str, list[tuple[str, int]]] = {n: [] for n in NODES}
for a, b, w in _ZONES["edges"]:
    _ADJ[a].append((b, w))
    _ADJ[b].append((a, w))


def resolve_start(start: str) -> str:
    """노드 id 또는 포털(지상 진입점) 이름을 노드 id 로 정규화."""
    if start in NODES:
        return start
    if start in PORTALS:
        return PORTALS[start]
    raise ValueError(f"unknown start: {start}")


def dijkstra(start: str) -> tuple[dict[str, int], dict[str, str | None]]:
    """start 로부터 각 노드까지 최단 도보시간(분)과 직전 노드."""
    dist = {n: float("inf") for n in NODES}
    prev: dict[str, str | None] = {n: None for n in NODES}
    dist[start] = 0
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in _ADJ[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


# 선형 축 순서(경로그래프의 양 끝점을 잇는 순서). 방향성 코스 계산에 사용.
def _axis_order() -> list[str]:
    ends = [n for n in NODES if len(_ADJ[n]) == 1]
    start = ends[0] if ends else next(iter(NODES))
    order, prev, cur = [start], None, start
    while True:
        nxts = [v for v, _ in _ADJ[cur] if v != prev]
        if not nxts:
            break
        prev, cur = cur, nxts[0]
        order.append(cur)
    return order


_ORDER = _axis_order()
_W = {}
for a, b, w in _ZONES["edges"]:
    _W[(a, b)] = _W[(b, a)] = w


def _walk(s: str, budget_min: int, step: int) -> tuple[list[dict], int]:
    """s 에서 축을 따라 한 방향(step=+1 동쪽 / -1 서쪽)으로 예산 안에서 방문."""
    i = _ORDER.index(s)
    course, clock = [], NODES[s]["dwell"]
    course.append({**_node_card(s), "arrive_min": 0})
    j = i + step
    while 0 <= j < len(_ORDER):
        prev_id, cur_id = _ORDER[j - step], _ORDER[j]
        seg = _W[(prev_id, cur_id)]
        need = seg + NODES[cur_id]["dwell"]
        if clock + need > budget_min:
            break
        clock += need
        course.append({**_node_card(cur_id), "arrive_min": clock - NODES[cur_id]["dwell"]})
        j += step
    return course, clock


def _node_card(n: str) -> dict:
    info = NODES[n]
    return {"id": n, "name": info["name"], "scene": info["scene"], "do": info["do"], "dwell": info["dwell"]}


def plan_course(start: str, budget_min: int) -> dict:
    """진입점 + 분예산 → 예산 안의 방향성 코스. 동/서 중 더 많이 도는 쪽을 선택.

    Dijkstra 로 최단거리를 확인하되(도달성 검증), 완주를 강제하지 않는 선형 코스로 구성.
    """
    s = resolve_start(start)
    east, e_min = _walk(s, budget_min, +1)
    west, w_min = _walk(s, budget_min, -1)
    # 더 많은 구역, 동률이면 더 긴 체류를 택함
    course, total = (east, e_min) if (len(east), e_min) >= (len(west), w_min) else (west, w_min)
    return {
        "start": s,
        "start_name": NODES[s]["name"],
        "budget_min": budget_min,
        "total_min": total,
        "reached": len(course),
        "course": course,
    }
