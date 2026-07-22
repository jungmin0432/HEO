from __future__ import annotations

import json
import csv
from datetime import datetime, timezone
from pathlib import Path

from services.benchmark import run_baseline_benchmark
from services.model_selection import inspect_resolution, select_restoration_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHOTO_ROOT = PROJECT_ROOT.parent / "photos"
PLACE_DATA = PROJECT_ROOT / "data" / "places.json"


def main() -> None:
    with PLACE_DATA.open(encoding="utf-8") as file:
        place = json.load(file)["places"][0]
    source = PHOTO_ROOT / place["historical_asset_path"]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = PROJECT_ROOT / "benchmarks" / timestamp

    profile = inspect_resolution(source)
    result = run_baseline_benchmark(source, output_dir)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "place_id": place["id"],
        "input_profile": profile.__dict__,
        "recommended_ai_plan": select_restoration_plan(profile).to_dict(),
        "results": [result],
        "selection_gate": {
            "rule": "AI 후보는 같은 controlled degradation에서 Pillow baseline보다 SSIM +0.01 또는 PSNR +0.3dB를 만족할 때만 기본 후보로 제시한다.",
            "human_review": "실제 역사사진에서는 정답 원본이 없으므로 원본·AI 결과·경고문을 함께 보며 운영자가 최종 선택한다."
        }
    }
    with (output_dir / "benchmark_report.json").open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    with (output_dir / "benchmark_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "created_at",
                "place_id",
                "input_width",
                "input_height",
                "input_megapixels",
                "recommended_plan",
                "candidate",
                "test_type",
                "psnr_db",
                "ssim",
                "edge_strength",
                "processing_time_ms",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "created_at": report["created_at"],
                "place_id": place["id"],
                "input_width": profile.width,
                "input_height": profile.height,
                "input_megapixels": profile.megapixels,
                "recommended_plan": report["recommended_ai_plan"]["plan_id"],
                "candidate": result["candidate"],
                "test_type": result["test_type"],
                "psnr_db": result["metrics"]["psnr_db"],
                "ssim": result["metrics"]["ssim"],
                "edge_strength": result["metrics"]["edge_strength"],
                "processing_time_ms": result["processing_time_ms"],
            }
        )
    print(output_dir)


if __name__ == "__main__":
    main()
