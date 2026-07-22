"""Build the local SQLite database for the QR route recommender.

Sources are deliberately separated by confidence:
* Official store directory: names and published hours (route use not yet allowed)
* Proposed route graph: demo nodes/edges that require field timing validation
* External destinations: official institution/space references

Run: python build_route_database.py
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "euljiro_route_20260722_project.db"
STORE_SNAPSHOT = DATA_DIR / "euljiro_underground_directory_hours.csv"
OFFICIAL_DIRECTORY_URL = "https://www.sisul.or.kr/gha/store/list.do?key=2309210002&sc_mallSn=1"


def time_from_text(value: str) -> str | None:
    match = re.search(r"([0-2]?\d)\s*:\s*([0-5]\d)", value or "")
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE sources (
          source_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          checked_at TEXT NOT NULL,
          scope TEXT NOT NULL,
          reliability TEXT NOT NULL
        );

        CREATE TABLE stores (
          store_id TEXT PRIMARY KEY,
          store_name TEXT NOT NULL,
          category TEXT,
          published_hours TEXT,
          open_time TEXT,
          close_time TEXT,
          weekday_rule TEXT,
          route_node_id TEXT,
          routable INTEGER NOT NULL DEFAULT 0,
          location_status TEXT NOT NULL,
          hours_status TEXT NOT NULL,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          checked_at TEXT NOT NULL
        );

        CREATE TABLE nodes (
          node_id TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          kind TEXT NOT NULL,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          validation_status TEXT NOT NULL
        );

        CREATE TABLE edges (
          edge_id TEXT PRIMARY KEY,
          from_node TEXT NOT NULL REFERENCES nodes(node_id),
          to_node TEXT NOT NULL REFERENCES nodes(node_id),
          estimated_minutes INTEGER NOT NULL,
          estimated_meters INTEGER NOT NULL,
          accessible INTEGER NOT NULL,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          validation_status TEXT NOT NULL
        );

        CREATE TABLE destinations (
          destination_id TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          node_id TEXT NOT NULL REFERENCES nodes(node_id),
          published_hours TEXT,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          validation_status TEXT NOT NULL
        );

        CREATE TABLE planned_spaces (
          space_id TEXT PRIMARY KEY,
          node_id TEXT NOT NULL REFERENCES nodes(node_id),
          zone TEXT NOT NULL,
          title TEXT NOT NULL,
          role TEXT NOT NULL,
          purpose_tags TEXT NOT NULL,
          expected_dwell_minutes INTEGER NOT NULL,
          operation_status TEXT NOT NULL,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          note TEXT NOT NULL
        );

        CREATE TABLE validation_tasks (
          task_id TEXT PRIMARY KEY,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          task TEXT NOT NULL,
          completion_rule TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'todo'
        );
        """
    )


def load_stores(conn: sqlite3.Connection, checked_at: str) -> int:
    with STORE_SNAPSHOT.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        conn.execute(
            """
            INSERT INTO stores (
              store_id, store_name, category, published_hours, open_time, close_time,
              weekday_rule, route_node_id, routable, location_status, hours_status,
              source_id, checked_at
            ) VALUES (?, ?, NULL, ?, ?, ?, 'official listing; holiday rule not published',
              NULL, 0, 'node not field-verified', ?, 'sisul_store_directory', ?)
            """,
            (
                row["store_id"],
                row["store_name"],
                row["published_hours"],
                time_from_text(row["published_hours"]),
                f"{int(row['parsed_close_hour']):02d}:{int(row['parsed_close_minute']):02d}"
                if row.get("parsed_close_hour") and row.get("parsed_close_minute")
                else None,
                "published" if row.get("parsed_close_hour") else "unparsed",
                checked_at,
            ),
        )
    return len(rows)


def load_route_graph(conn: sqlite3.Connection) -> None:
    # These labels match the prototype screen. Distances/times are intentionally
    # flagged as field-validation required, not represented as an official survey.
    nodes = [
        ("E1_GATE", "을지로입구 서쪽 QR 게이트", "gate"),
        ("E1_HALL", "을지로입구 전시·상품 구간", "zone"),
        ("E3_WEST", "을지로3가 서측 QR 게이트", "gate"),
        ("E3_CENTER", "을지로3가 기억·쉼터 구간", "zone"),
        ("E3_EAST", "을지로3가 동측 연결부", "junction"),
        ("E4_WEST", "을지로4가 서측 연결부", "junction"),
        ("E4_CENTER", "을지로4가 제작·상담 구간", "zone"),
        ("E4_EAST", "을지로4가 동측 QR 게이트", "gate"),
        ("DDP_GATE", "DDP 연결부 QR 게이트", "gate"),
        ("CHEONGGYE_ENTRY", "청계천 연결 목적지", "external_destination"),
        ("HIPJIRO_EXIT", "힙지로 연결 목적지", "external_destination"),
        ("BANGSAN_EXIT", "방산시장 연결 목적지", "external_destination"),
    ]
    conn.executemany(
        "INSERT INTO nodes VALUES (?, ?, ?, 'prototype_route_graph', 'needs_field_validation')",
        nodes,
    )
    edges = [
        ("edge-01", "E1_GATE", "E1_HALL", 3, 180, 1),
        ("edge-02", "E1_HALL", "E3_WEST", 6, 410, 1),
        ("edge-03", "E3_WEST", "E3_CENTER", 4, 250, 1),
        ("edge-04", "E3_CENTER", "E3_EAST", 4, 260, 1),
        ("edge-05", "E3_EAST", "E4_WEST", 6, 390, 1),
        ("edge-06", "E4_WEST", "E4_CENTER", 4, 250, 1),
        ("edge-07", "E4_CENTER", "E4_EAST", 4, 260, 1),
        ("edge-08", "E4_EAST", "DDP_GATE", 7, 470, 1),
    ]
    conn.executemany(
        "INSERT INTO edges VALUES (?, ?, ?, ?, ?, ?, 'prototype_route_graph', 'needs_field_validation')",
        edges,
    )
    conn.executemany(
        """
        INSERT INTO validation_tasks(task_id, entity_type, entity_id, task, completion_rule)
        VALUES (?, 'edge', ?, '평일·주말 각각 3회 보행시간 측정',
                '중앙값으로 estimated_minutes 갱신, 엘리베이터 우회경로 별도 등록')
        """,
        [(f"survey-{edge[0]}", edge[0]) for edge in edges],
    )


def load_destinations(conn: sqlite3.Connection) -> None:
    # Destination is a routing anchor. Program/exhibition hours should be supplied
    # per event and must not be conflated with DDP building access hours.
    conn.executemany(
        "INSERT INTO destinations VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "DDP",
                "DDP 연결부",
                "DDP_GATE",
                None,
                "ddp_guide",
                "공식 목적지. 전시·매장별 운영시간은 개별 확인 필요",
            ),
            (
                "CHEONGGYE",
                "청계천",
                "CHEONGGYE_ENTRY",
                None,
                "cheonggye_guide",
                "공공 보행공간. 수변 시설 운영시간은 시설별로 다름",
            ),
            (
                "HIPJIRO",
                "힙지로",
                "HIPJIRO_EXIT",
                None,
                "seoul_market_reference",
                "개별 점포 상권. 통합 영업시간 없음",
            ),
            (
                "BANGSAN",
                "방산시장",
                "BANGSAN_EXIT",
                None,
                "seoul_market_reference",
                "개별 점포 상권. 통합 영업시간 없음",
            ),
        ],
    )


def load_planned_spaces(conn: sqlite3.Connection) -> None:
    """Project-design spaces that must appear in the post-redevelopment route."""
    spaces = [
        ("plan-e1-panorama", "E1_HALL", "E1", "서울 시간 파노라마", "첫 발견·장면 선택", "look,memory,move", 4),
        ("plan-e1-sample", "E1_HALL", "E1", "서울 한 장 샘플 바", "첫 구매·당일상품 확인", "look,make", 6),
        ("plan-e3-archive", "E3_CENTER", "E3", "기억 아카이브 월", "체류·역사장면 비교", "look,memory", 6),
        ("plan-e3-restore", "E3_CENTER", "E3", "AI 사진복원 스테이션", "사진복원 미리보기·인화 연결", "memory", 6),
        ("plan-e3-editor", "E3_CENTER", "E3", "가족 기록 편집 테이블", "사진·문장 선택·미니 시간책 편집", "family,memory", 8),
        ("plan-e4-material", "E4_CENTER", "E4", "제작 재료 라이브러리", "종이·원단·마감 샘플 비교", "look,make", 6),
        ("plan-e4-translate", "E4_CENTER", "E4", "AI 제작통역 스테이션", "말·사진·외국어를 제작요청서로 변환", "make", 5),
        ("plan-e4-demo", "E4_CENTER", "E4", "메이커 시연 포켓", "인쇄·마킹·수선 공정 관람", "look,make,family", 8),
        ("plan-ddp-wall", "DDP_GATE", "DDP", "도시 시간중첩 월", "DDP·훈련원·동대문운동장 비교", "look,memory,move", 5),
        ("plan-ddp-pickup", "DDP_GATE", "DDP", "완성품 쇼케이스·픽업", "수령·촬영·지상 상권 연결", "look,make,memory", 5),
    ]
    conn.executemany(
        """
        INSERT INTO planned_spaces VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', 'project_design', ?)
        """,
        [
            (*space, "경진대회 제안 공간. 조성 전에는 실제 영업시간·혼잡도 대신 설계 체류시간을 사용")
            for space in spaces
        ],
    )


def build() -> dict[str, int | str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    checked_at = date.today().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        create_schema(conn)
        conn.executemany(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "sisul_store_directory",
                    "서울시설공단 지하도상가 을지로 점포안내",
                    OFFICIAL_DIRECTORY_URL,
                    checked_at,
                    "공개 점포명·게시 영업시간",
                    "official",
                ),
                (
                    "prototype_route_graph",
                    "서울 아랫길 600년 MVP 통로 그래프",
                    "local://field-survey-required",
                    checked_at,
                    "프로토타입 노드·구간시간; 현장측정 전",
                    "needs_field_validation",
                ),
                (
                    "project_design",
                    "서울 아랫길 600년 공간조성안",
                    "local://project-proposal",
                    checked_at,
                    "을지로입구·을지로3가·을지로4가·DDP 연결부 신규 조성 예정 공간",
                    "project_design",
                ),
                (
                    "ddp_guide",
                    "DDP 공식 안내",
                    "https://www.ddp.or.kr/",
                    checked_at,
                    "DDP 연결 목적지",
                    "official",
                ),
                (
                    "cheonggye_guide",
                    "서울시설공단 청계천 시설물 안내",
                    "https://www.sisul.or.kr/open_content/cheonggye/intro/facility.jsp",
                    checked_at,
                    "청계천 연결 목적지·시설별 운영시간",
                    "official",
                ),
                (
                    "seoul_market_reference",
                    "서울시 전통시장 현황",
                    "https://news.seoul.go.kr/economy/archives/66052",
                    checked_at,
                    "방산시장 등 연결 상권의 위치 참고",
                    "official_reference",
                ),
            ],
        )
        store_count = load_stores(conn, checked_at)
        load_route_graph(conn)
        load_destinations(conn)
        load_planned_spaces(conn)
        summary = {
            "database": str(DB_PATH),
            "checked_at": checked_at,
            "official_store_count": store_count,
            "routable_store_count": conn.execute("SELECT COUNT(*) FROM stores WHERE routable=1").fetchone()[0],
            "route_nodes": conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
            "planned_space_count": conn.execute("SELECT COUNT(*) FROM planned_spaces").fetchone()[0],
            "route_edges_needing_field_validation": conn.execute(
                "SELECT COUNT(*) FROM edges WHERE validation_status='needs_field_validation'"
            ).fetchone()[0],
        }
        (DATA_DIR / "database_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
