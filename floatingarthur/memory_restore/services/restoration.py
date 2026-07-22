from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from services.model_selection import inspect_resolution, select_restoration_plan
from services.realesrgan_adapter import AIBackendUnavailable, run_realesrgan


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_jpeg(image: Image.Image, target: Path) -> None:
    image.convert("RGB").save(target, "JPEG", quality=95, optimize=True)


def create_baseline_restoration(
    source: Path,
    output_root: Path,
    source_type: str,
    source_attribution: str,
    place_id: str | None = None,
) -> dict:
    """Create non-generative comparison variants without changing the source file."""
    if not source.is_file():
        raise FileNotFoundError(source)

    created_at = datetime.now(timezone.utc)
    record_id = f"baseline-{created_at:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    result_dir = output_root / record_id
    result_dir.mkdir(parents=True, exist_ok=False)

    original_copy = result_dir / f"original{source.suffix.lower()}"
    shutil.copy2(source, original_copy)

    with Image.open(source) as opened:
        original = ImageOps.exif_transpose(opened).convert("RGB")
        input_resolution = f"{original.width} x {original.height}"

        conservative = ImageOps.autocontrast(original, cutoff=0.5)
        conservative = conservative.filter(ImageFilter.MedianFilter(size=3))
        conservative = conservative.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=5))
        conservative = ImageEnhance.Brightness(conservative).enhance(1.02)
        _save_jpeg(conservative, result_dir / "conservative.jpg")

        expressive = ImageOps.autocontrast(original, cutoff=1.0)
        expressive = expressive.filter(ImageFilter.MedianFilter(size=3))
        expressive = expressive.filter(ImageFilter.UnsharpMask(radius=1.8, percent=115, threshold=3))
        expressive = ImageEnhance.Contrast(expressive).enhance(1.12)
        expressive = ImageEnhance.Color(expressive).enhance(1.08)
        _save_jpeg(expressive, result_dir / "expressive.jpg")

    output_resolution = input_resolution
    record = {
        "record_id": record_id,
        "created_at": created_at.isoformat(),
        "source_type": source_type,
        "place_id": place_id,
        "original_filename": source.name,
        "original_sha256": sha256_of(source),
        "original_copy_sha256": sha256_of(original_copy),
        "input_resolution": input_resolution,
        "output_resolution": output_resolution,
        "variants": {
            "preserve": {
                "file": original_copy.name,
                "label": "원본 보존",
                "description": "원본 파일을 바꾸지 않고 사본만 보관합니다.",
            },
            "conservative": {
                "file": "conservative.jpg",
                "label": "보수형 보정",
                "description": "가벼운 대비 조정, 노이즈 완화, 선명도 보정을 적용합니다.",
            },
            "expressive": {
                "file": "expressive.jpg",
                "label": "표현형 보정",
                "description": "대비와 선명도를 더 강하게 조정한 비교 시안입니다.",
            },
        },
        "pipeline": [
            {
                "name": "Pillow baseline image processing",
                "settings": {
                    "generative_ai": False,
                    "face_enhancement": False,
                    "colorization": False,
                    "upscaling": False,
                },
            }
        ],
        "warnings": [
            "이 결과는 생성형 AI 복원이 아닌 기준선 이미지 보정입니다.",
            "보정 결과는 원본의 역사적 사실을 추가로 증명하지 않습니다.",
            "표현형 보정은 대비와 선명도가 강화되어 인쇄 전 원본과 함께 확인해야 합니다.",
        ],
        "ai_marked": False,
        "intended_print_size": None,
        "source_attribution": source_attribution,
    }
    with (result_dir / "restoration_record.json").open("w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2)
    return record


def create_upload_restoration(
    source: Path,
    output_root: Path,
    source_attribution: str,
    place_id: str | None,
    request_ai: bool,
    source_type: str = "user_upload",
    historical_context: dict | None = None,
) -> dict:
    """Create a traceable local-demo restoration, optionally adding a GPU output."""
    record = create_baseline_restoration(
        source=source,
        output_root=output_root,
        source_type=source_type,
        source_attribution=source_attribution,
        place_id=place_id,
    )
    result_dir = output_root / record["record_id"]
    profile = inspect_resolution(source)
    plan = select_restoration_plan(profile)
    record["input_profile"] = {
        "width": profile.width,
        "height": profile.height,
        "megapixels": profile.megapixels,
    }
    record["restoration_plan"] = plan.to_dict()
    if historical_context:
        record["historical_context"] = historical_context
    record["ai_status"] = "not_requested"

    if request_ai and plan.model_name:
        try:
            original_copy = result_dir / record["variants"]["preserve"]["file"]
            # The official worker writes in the source format. Keep the extension aligned
            # so Flask serves PNG/WebP results with the correct media type.
            ai_output = result_dir / f"ai_restored{original_copy.suffix.lower()}"
            pipeline_entry = run_realesrgan(
                input_path=original_copy,
                output_path=ai_output,
                outscale=plan.outscale,
                model_name=plan.model_name,
            )
        except AIBackendUnavailable:
            record["ai_status"] = "unavailable"
            record["warnings"].append(
                "AI restoration was requested, but the local GPU worker is not enabled. "
                "Set ENABLE_LOCAL_REALESRGAN=1 only in a prepared CUDA environment."
            )
        else:
            with Image.open(ai_output) as restored:
                record["output_resolution"] = f"{restored.width} x {restored.height}"
            record["variants"]["ai_restored"] = {
                "file": ai_output.name,
                "label": "AI restoration",
                "description": "General-image Real-ESRGAN output. Compare it with the preserved original.",
            }
            record["pipeline"].append(pipeline_entry)
            record["ai_status"] = "completed"
            record["ai_marked"] = True
    elif request_ai:
        record["ai_status"] = "preserve_priority"
        record["warnings"].append(
            "The input is already high resolution, so the preservation-first plan does not run AI upscaling."
        )

    record["change_explanations"] = build_change_explanations(record)

    with (result_dir / "restoration_record.json").open("w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2)
    return record


def build_change_explanations(record: dict) -> list[dict]:
    """Describe each output's method and limits without claiming historical truth."""
    explanations = [
        {
            "variant_id": "preserve",
            "title": "원본 보존",
            "what_changed": "이미지 내용은 바꾸지 않았고, 업로드 원본의 사본만 결과 기록에 연결했습니다.",
            "basis": "원본 파일의 SHA-256 해시와 원본 사본 해시를 기록해 동일성을 확인합니다.",
            "limit": "원본 자체가 촬영 당시의 모든 사실을 증명하는 것은 아닙니다.",
        },
        {
            "variant_id": "conservative",
            "title": "보수 보정",
            "what_changed": "약한 자동 대비, 메디안 노이즈 완화, 제한적 선명도와 밝기 보정을 적용했습니다.",
            "basis": "Pillow 기준선 파이프라인의 고정 설정으로 재현 가능한 비교본입니다.",
            "limit": "가려졌거나 손실된 물체를 새로 만들어 내지 않습니다.",
        },
        {
            "variant_id": "expressive",
            "title": "표현 보정",
            "what_changed": "보수 보정보다 대비와 선명도, 색감을 더 강하게 조정했습니다.",
            "basis": "원본과 보수 보정본을 함께 놓고 조정 강도의 차이를 확인하기 위한 비교안입니다.",
            "limit": "강한 표현은 실제 장면의 색·명암을 더 정확하게 복원했다는 뜻이 아닙니다.",
        },
    ]
    if "ai_restored" in record.get("variants", {}):
        plan = record.get("restoration_plan", {})
        explanations.append(
            {
                "variant_id": "ai_restored",
                "title": "AI 복원",
                "what_changed": "일반 이미지 복원 모델이 해상도와 질감을 추정해 출력한 비교 결과입니다.",
                "basis": (
                    f"입력 {record.get('input_resolution')}에 대해 {plan.get('plan_id')} 계획을 선택하고, "
                    f"{plan.get('model_name')} 모델을 x{plan.get('outscale')}로 실행했습니다."
                ),
                "limit": "새로 선명해진 세부 묘사는 모델의 추정일 수 있으며, 역사적 사실이나 원래 장면을 추가로 증명하지 않습니다.",
            }
        )
    return explanations
