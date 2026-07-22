from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


DB_PATH = Path(__file__).resolve().parent / "data" / "euljiro_route_20260722_project.db"
SEOUL = ZoneInfo("Asia/Seoul")


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError("데이터베이스가 없습니다. python build_route_database.py 를 먼저 실행하세요.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def database_status() -> dict:
    with _connect() as conn:
        return {
            "official_store_count": conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0],
            "routable_store_count": conn.execute("SELECT COUNT(*) FROM stores WHERE routable=1").fetchone()[0],
            "route_nodes": conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
            "route_edges_field_verified": conn.execute(
                "SELECT COUNT(*) FROM edges WHERE validation_status='field_verified'"
            ).fetchone()[0],
            "route_edges_needing_field_validation": conn.execute(
                "SELECT COUNT(*) FROM edges WHERE validation_status!='field_verified'"
            ).fetchone()[0],
            "planned_space_count": conn.execute("SELECT COUNT(*) FROM planned_spaces").fetchone()[0],
            "warning": "공식 점포명·게시 영업시간은 적재됨. 점포 위치와 통로 보행시간은 현장검증 전까지 자동 추천에 사용하지 않음.",
        }


def list_stores(query: str = "", limit: int = 50) -> list[dict]:
    keyword = f"%{query.strip()}%"
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT store_id, store_name, published_hours, open_time, close_time,
                   routable, location_status, hours_status, checked_at
            FROM stores
            WHERE store_name LIKE ?
            ORDER BY store_name
            LIMIT ?
            """,
            (keyword, min(max(int(limit), 1), 100)),
        ).fetchall()
    return [dict(row) for row in rows]


def list_planned_spaces() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT space_id, node_id, zone, title, role, purpose_tags,
                   expected_dwell_minutes, operation_status, note
            FROM planned_spaces
            ORDER BY CASE zone WHEN 'E1' THEN 1 WHEN 'E3' THEN 2 WHEN 'E4' THEN 3 ELSE 4 END,
                     expected_dwell_minutes, title
            """
        ).fetchall()
    return [dict(row) for row in rows]


def stores_open_now(query: str = "", now: datetime | None = None) -> list[dict]:
    """Return only stores whose *published daily time range* is currently open.

    Holiday and temporary closure are intentionally not inferred here; the client
    must present this as 'published-hours match' until a merchant status feed exists.
    """
    current = now or datetime.now(SEOUL)
    now_minutes = current.hour * 60 + current.minute
    result = []
    for store in list_stores(query, 100):
        if not store["open_time"] or not store["close_time"]:
            continue
        open_hour, open_minute = map(int, store["open_time"].split(":"))
        close_hour, close_minute = map(int, store["close_time"].split(":"))
        if open_hour * 60 + open_minute <= now_minutes < close_hour * 60 + close_minute:
            store["open_status"] = "published_hours_match"
            result.append(store)
    return result
