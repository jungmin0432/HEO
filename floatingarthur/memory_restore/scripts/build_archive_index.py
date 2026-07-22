"""Create a source-backed starter index for the historical-image feature cache."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "cache" / "location_matching" / "manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "archive_index.json"
SEOUL_METRO_COORDINATE_SOURCE = "https://data.seoul.go.kr/dataList/OA-22534/F/1/datasetView.do"


SERIES = {
    "euljiro_entrance_surroundings_1983": {
        "title": "을지로입구 주변 촬영",
        "year": 1983,
        "source_url": "https://archives.seoul.go.kr/item/4356",
        "zone": "euljiro-entrance",
        "landmark_tags": ["을지로입구역", "을지로입구", "지상 출입구", "지하 연결"],
        "location": {
            "latitude": 37.566111,
            "longitude": 126.9825,
            "radius_m": 220,
            "scope": "station_area_anchor",
            "source_url": SEOUL_METRO_COORDINATE_SOURCE,
        },
    },
    "euljiro_entrance_underpass_construction_1976": {
        "title": "을지로입구 지하도 착공",
        "year": 1976,
        "source_url": "https://archives.seoul.go.kr/item/2610",
        "zone": "euljiro-entrance",
        "landmark_tags": ["을지로입구역", "지하도", "공사", "출입구", "지하상가"],
        "location": {
            "latitude": 37.566111,
            "longitude": 126.9825,
            "radius_m": 220,
            "scope": "station_area_anchor",
            "source_url": SEOUL_METRO_COORDINATE_SOURCE,
        },
    },
    "euljiro_line2_opening_1983": {
        "title": "서울 지하철 2호선 을지로구간 개통",
        "year": 1983,
        "source_url": "https://archives.seoul.go.kr/item/0000000000002157",
        "zone": "euljiro-3ga",
        "landmark_tags": ["을지로3가역", "을지로2호선", "지하 연결 통로", "지하상가"],
        "location": {
            "latitude": 37.56629,
            "longitude": 126.99278,
            "radius_m": 240,
            "scope": "station_area_anchor",
            "source_url": SEOUL_METRO_COORDINATE_SOURCE,
        },
    },
}


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assets = []
    for image in manifest["images"]:
        relative_path = image["relative_path"]
        series_id = relative_path.split("/", 1)[0]
        if series_id not in SERIES:
            raise KeyError(f"No series metadata configured for {relative_path}")
        series = SERIES[series_id]
        assets.append(
            {
                "asset_id": image["asset_id"],
                "relative_path": relative_path,
                "sha256": image["sha256"],
                "archive": {
                    "title": series["title"],
                    "year": series["year"],
                    "source_url": series["source_url"],
                },
                "zone": series["zone"],
                "landmark_tags": series["landmark_tags"],
                "location": series["location"],
                "verification_level": "STATION_AREA_ANCHOR",
                "matching_note": "역세권 앵커는 후보 축소용이며 과거 사진의 정확한 촬영 지점을 의미하지 않습니다.",
            }
        )
    payload = {
        "version": "starter-2026-07",
        "coordinate_policy": "Station-area anchors only. Never present them as exact historical camera positions.",
        "assets": assets,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(assets)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
