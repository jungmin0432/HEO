from __future__ import annotations

import json
from pathlib import Path

from services.restoration import create_baseline_restoration


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHOTO_ROOT = PROJECT_ROOT.parent / "photos"
PLACE_DATA = PROJECT_ROOT / "data" / "places.json"


def main() -> None:
    with PLACE_DATA.open(encoding="utf-8") as file:
        place = json.load(file)["places"][0]

    record = create_baseline_restoration(
        source=PHOTO_ROOT / place["historical_asset_path"],
        output_root=PROJECT_ROOT / "outputs",
        source_type="archive",
        source_attribution=place["archive"]["attribution"],
        place_id=place["id"],
    )
    print(record["record_id"])


if __name__ == "__main__":
    main()
