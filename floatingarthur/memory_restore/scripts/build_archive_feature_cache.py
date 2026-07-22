"""Build reusable CLIP and DINOv2 features for the public historical archive.

This is a preparation tool, not a location decision service. It stores vectors,
pairwise similarities, and attention summaries for later retrieval experiments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel, CLIPModel, CLIPProcessor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PHOTO_ROOT = PROJECT_ROOT.parent / "photos" / "history_photo"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "cache" / "location_matching"
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo-root", type=Path, default=DEFAULT_PHOTO_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--clip-model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--dino-model", default="facebook/dinov2-small")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N images for a smoke test.")
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Allow an initial model download. Later cache builds should remain offline and reproducible.",
    )
    return parser.parse_args()


def resolve_device(requested: str) -> torch.device:
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available in this runtime.")
        return torch.device("cuda")
    if requested == "cpu":
        return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def list_images(photo_root: Path, limit: int | None) -> list[Path]:
    paths = sorted(path for path in photo_root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES)
    return paths[:limit] if limit else paths


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(vector: torch.Tensor) -> np.ndarray:
    vector = torch.nn.functional.normalize(vector, dim=-1)
    return vector.squeeze(0).detach().cpu().numpy().astype(np.float32)


def attention_map(attentions: tuple[torch.Tensor, ...]) -> tuple[np.ndarray, dict[str, float]]:
    # Last-layer attention from CLS token to image patches. It is a visual
    # importance cue, not a geographic or historical-match probability.
    weights = attentions[-1][0].mean(dim=0)[0, 1:].detach().cpu().numpy().astype(np.float32)
    side = int(round(weights.size ** 0.5))
    if side * side != weights.size:
        raise RuntimeError(f"Unexpected DINOv2 patch count: {weights.size}")
    weights = weights.reshape(side, side)
    total = float(weights.sum())
    distribution = weights / total if total else weights
    non_zero = distribution[distribution > 0]
    entropy = float(-(non_zero * np.log(non_zero)).sum()) if non_zero.size else 0.0
    top_fraction = float(np.sort(distribution.ravel())[-min(10, distribution.size):].sum())
    return weights, {
        "max_attention": float(distribution.max()) if distribution.size else 0.0,
        "attention_entropy": entropy,
        "top_10_patch_fraction": top_fraction,
    }


def main() -> None:
    args = parse_args()
    if not args.photo_root.is_dir():
        raise FileNotFoundError(f"Historical photo root not found: {args.photo_root}")
    paths = list_images(args.photo_root, args.limit)
    if not paths:
        raise RuntimeError("No JPG, JPEG, PNG, or WebP historical images were found.")

    device = resolve_device(args.device)
    args.output_root.mkdir(parents=True, exist_ok=True)

    loader_options = {"local_files_only": not args.allow_download}
    clip_processor = CLIPProcessor.from_pretrained(args.clip_model, **loader_options)
    clip_model = CLIPModel.from_pretrained(args.clip_model, **loader_options).to(device).eval()
    dino_processor = AutoImageProcessor.from_pretrained(args.dino_model, **loader_options)
    dino_model = AutoModel.from_pretrained(args.dino_model, **loader_options).to(device).eval()

    clip_vectors: list[np.ndarray] = []
    dino_vectors: list[np.ndarray] = []
    attention_maps: list[np.ndarray] = []
    manifest_images: list[dict] = []
    attention_summaries: dict[str, dict[str, float]] = {}

    with torch.inference_mode():
        for index, path in enumerate(paths, start=1):
            with Image.open(path) as source:
                image = source.convert("RGB")

            clip_inputs = clip_processor(images=image, return_tensors="pt")
            clip_inputs = {name: value.to(device) for name, value in clip_inputs.items()}
            clip_vectors.append(normalized(clip_model.get_image_features(**clip_inputs)))

            dino_inputs = dino_processor(images=image, return_tensors="pt")
            dino_inputs = {name: value.to(device) for name, value in dino_inputs.items()}
            dino_outputs = dino_model(**dino_inputs, output_attentions=True)
            dino_vectors.append(normalized(dino_outputs.pooler_output))
            patch_attention, summary = attention_map(dino_outputs.attentions)
            attention_maps.append(patch_attention)

            asset_id = path.relative_to(args.photo_root).as_posix()
            manifest_images.append({
                "asset_id": asset_id,
                "relative_path": asset_id,
                "sha256": sha256(path),
                "width": image.width,
                "height": image.height,
            })
            attention_summaries[asset_id] = summary
            print(f"[{index}/{len(paths)}] {asset_id}")

    clip_matrix = np.stack(clip_vectors)
    dino_matrix = np.stack(dino_vectors)
    np.save(args.output_root / "clip_embeddings.npy", clip_matrix)
    np.save(args.output_root / "dino_embeddings.npy", dino_matrix)
    np.save(args.output_root / "clip_similarity.npy", clip_matrix @ clip_matrix.T)
    np.save(args.output_root / "dino_similarity.npy", dino_matrix @ dino_matrix.T)
    np.save(args.output_root / "dino_attention_maps.npy", np.stack(attention_maps))

    (args.output_root / "attention_summary.json").write_text(
        json.dumps(attention_summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "device": str(device),
        "clip_model": args.clip_model,
        "dino_model": args.dino_model,
        "offline_model_load": not args.allow_download,
        "image_count": len(manifest_images),
        "images": manifest_images,
        "notes": [
            "Pairwise similarity is cosine similarity between normalized image embeddings.",
            "Attention summaries are visual importance cues and do not identify a geographic location.",
            "No location-match score is stored at this stage because verified coordinate metadata is not yet complete.",
        ],
    }
    (args.output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Feature cache written to {args.output_root}")


if __name__ == "__main__":
    main()
