from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


def degrade_for_controlled_test(reference: Image.Image) -> Image.Image:
    """Create a repeatable low-resolution/JPEG-like input from a reference image."""
    rgb = ImageOps.exif_transpose(reference).convert("RGB")
    reduced = rgb.resize((max(1, rgb.width // 2), max(1, rgb.height // 2)), Image.Resampling.LANCZOS)
    # Re-encode through JPEG bytes to apply a controlled compression loss.
    from io import BytesIO

    buffer = BytesIO()
    reduced.save(buffer, "JPEG", quality=35)
    buffer.seek(0)
    with Image.open(buffer) as compressed:
        return compressed.convert("RGB").copy()


def baseline_upscale(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    restored = image.resize(target_size, Image.Resampling.LANCZOS)
    restored = ImageOps.autocontrast(restored, cutoff=0.5)
    return ImageEnhance.Contrast(restored).enhance(1.03)


def calculate_metrics(reference: Image.Image, candidate: Image.Image) -> dict:
    target = reference.convert("RGB")
    comparison = candidate.convert("RGB").resize(target.size, Image.Resampling.LANCZOS)
    reference_array = np.asarray(target, dtype=np.uint8)
    candidate_array = np.asarray(comparison, dtype=np.uint8)

    edge_x = np.diff(candidate_array.astype(np.float32), axis=1)
    edge_y = np.diff(candidate_array.astype(np.float32), axis=0)
    edge_strength = float((np.mean(np.abs(edge_x)) + np.mean(np.abs(edge_y))) / 2)
    return {
        "psnr_db": round(float(peak_signal_noise_ratio(reference_array, candidate_array, data_range=255)), 3),
        "ssim": round(float(structural_similarity(reference_array, candidate_array, channel_axis=2, data_range=255)), 5),
        "edge_strength": round(edge_strength, 3),
    }


def run_baseline_benchmark(source_path: Path, output_dir: Path) -> dict:
    """Benchmark a classical baseline on a controlled degradation; not on the historic original itself."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as opened:
        reference = ImageOps.exif_transpose(opened).convert("RGB")

    degraded = degrade_for_controlled_test(reference)
    started = time.perf_counter()
    restored = baseline_upscale(degraded, reference.size)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    reference.save(output_dir / "reference.jpg", "JPEG", quality=95)
    degraded.save(output_dir / "degraded_input.jpg", "JPEG", quality=95)
    restored.save(output_dir / "pillow_baseline.jpg", "JPEG", quality=95)
    return {
        "candidate": "Pillow baseline",
        "test_type": "controlled degradation",
        "source_filename": source_path.name,
        "metrics": calculate_metrics(reference, restored),
        "processing_time_ms": elapsed_ms,
        "note": "Real-ESRGAN 결과가 준비되면 동일 degraded_input.jpg와 reference.jpg로 비교한다.",
    }
