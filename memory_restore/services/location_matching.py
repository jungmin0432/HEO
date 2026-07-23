"""Historical-record candidate retrieval using cached CLIP and DINOv2 features."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


class LocationMatchingError(RuntimeError):
    """Raised when a location-match request cannot be evaluated safely."""


@dataclass(frozen=True)
class MatchRequest:
    photo_path: Path
    latitude: float | None = None
    longitude: float | None = None
    gps_accuracy_m: float | None = None
    landmark_text: str = ""
    limit: int = 5


class HistoricalLocationMatcher:
    """Loads fixed archive features once and embeds only the incoming photo."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.cache_root = project_root / "cache" / "location_matching"
        self.index_path = project_root / "data" / "archive_index.json"
        self._models_loaded = False
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            self.manifest = json.loads((self.cache_root / "manifest.json").read_text(encoding="utf-8"))
            index_payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.assets = index_payload["assets"]
            self.clip_embeddings = np.load(self.cache_root / "clip_embeddings.npy")
            self.dino_embeddings = np.load(self.cache_root / "dino_embeddings.npy")
        except (OSError, KeyError, json.JSONDecodeError) as error:
            raise LocationMatchingError(f"Location-match cache is unavailable: {error}") from error

        manifest_ids = [item["asset_id"] for item in self.manifest["images"]]
        index_ids = [item["asset_id"] for item in self.assets]
        if manifest_ids != index_ids:
            raise LocationMatchingError("Archive index order does not match the feature-cache manifest.")
        if len(self.assets) != len(self.clip_embeddings) or len(self.assets) != len(self.dino_embeddings):
            raise LocationMatchingError("Archive index and feature-cache row counts do not match.")

    def status(self) -> dict:
        anchored = sum(1 for asset in self.assets if asset.get("location", {}).get("latitude") is not None)
        return {
            "available": True,
            "asset_count": len(self.assets),
            "anchored_asset_count": anchored,
            "clip_model": self.manifest["clip_model"],
            "dino_model": self.manifest["dino_model"],
            "index_version": json.loads(self.index_path.read_text(encoding="utf-8"))["version"],
            "coordinate_policy": "station_area_anchor_only",
        }

    def find_candidates(self, match_request: MatchRequest) -> dict:
        self._validate_request(match_request)
        clip_vector, dino_vector = self._embed_image(match_request.photo_path)
        clip_similarity = self.clip_embeddings @ clip_vector
        dino_similarity = self.dino_embeddings @ dino_vector
        clip_score = self._percentile_score(clip_similarity)
        dino_score = self._percentile_score(dino_similarity)

        gps_present = match_request.latitude is not None and match_request.longitude is not None
        landmark_tokens = self._tokens(match_request.landmark_text)
        rows = []
        for index, asset in enumerate(self.assets):
            geo_score, geo_reason = self._geo_score(asset, match_request) if gps_present else (None, "GPS 미입력")
            landmark_score, landmark_reason = self._landmark_score(asset, landmark_tokens)
            score, score_parts = self._combine_scores(
                clip_score[index], dino_score[index], geo_score, landmark_score, gps_present, bool(landmark_tokens)
            )
            rows.append(
                {
                    "asset": asset,
                    "score": score,
                    "score_parts": score_parts,
                    "clip_rank": int(np.sum(clip_similarity > clip_similarity[index])) + 1,
                    "dino_rank": int(np.sum(dino_similarity > dino_similarity[index])) + 1,
                    "geo_reason": geo_reason,
                    "landmark_reason": landmark_reason,
                }
            )

        rows.sort(key=lambda item: item["score"], reverse=True)
        candidates = [self._candidate_payload(row, rank + 1) for rank, row in enumerate(rows[: match_request.limit])]
        top = rows[0]
        hold = top["score"] < 56 or (not gps_present and not landmark_tokens and top["score"] < 68)
        return {
            "decision": "HOLD" if hold else "CANDIDATES",
            "decision_note": (
                "입력 단서가 충분하지 않아 특정 기록을 추천하지 않습니다. 후보는 탐색용으로만 확인해 주세요."
                if hold
                else "후보는 기록 탐색을 돕는 순위이며 동일 촬영 지점을 확정하지 않습니다."
            ),
            "input_summary": {
                "gps_used": gps_present,
                "gps_accuracy_m": match_request.gps_accuracy_m,
                "landmark_text": match_request.landmark_text,
            },
            "model_version": f"{self.manifest['clip_model']} + {self.manifest['dino_model']}",
            "index_version": json.loads(self.index_path.read_text(encoding="utf-8"))["version"],
            "candidates": candidates,
        }

    def _embed_image(self, photo_path: Path) -> tuple[np.ndarray, np.ndarray]:
        self._ensure_models()
        with Image.open(photo_path) as source:
            image = source.convert("RGB")
        with self.torch.inference_mode():
            clip_inputs = self.clip_processor(images=image, return_tensors="pt")
            clip_inputs = {name: value.to(self.device) for name, value in clip_inputs.items()}
            clip_vector = self._normalized(self.clip_model.get_image_features(**clip_inputs))

            dino_inputs = self.dino_processor(images=image, return_tensors="pt")
            dino_inputs = {name: value.to(self.device) for name, value in dino_inputs.items()}
            dino_vector = self._normalized(self.dino_model(**dino_inputs).pooler_output)
        return clip_vector, dino_vector

    def _ensure_models(self) -> None:
        if self._models_loaded:
            return
        os.environ.setdefault("HF_HOME", str(self.project_root / "cache" / "huggingface"))
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModel, CLIPModel, CLIPProcessor
        except ImportError as error:
            raise LocationMatchingError("Location-matching runtime dependencies are not installed.") from error

        requested_device = os.getenv("LOCATION_MATCHING_DEVICE", "auto")
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise LocationMatchingError("LOCATION_MATCHING_DEVICE=cuda but CUDA is unavailable.")
        resolved_device = "cuda" if requested_device == "auto" and torch.cuda.is_available() else "cpu" if requested_device == "auto" else requested_device
        self.device = torch.device(resolved_device)
        loader_options = {"local_files_only": True}
        try:
            self.clip_processor = CLIPProcessor.from_pretrained(self.manifest["clip_model"], **loader_options)
            self.clip_model = CLIPModel.from_pretrained(self.manifest["clip_model"], **loader_options).to(self.device).eval()
            self.dino_processor = AutoImageProcessor.from_pretrained(self.manifest["dino_model"], **loader_options)
            self.dino_model = AutoModel.from_pretrained(self.manifest["dino_model"], **loader_options).to(self.device).eval()
        except OSError as error:
            raise LocationMatchingError("Pretrained model files are absent from the local Hugging Face cache.") from error
        self.torch = torch
        self._models_loaded = True

    @staticmethod
    def _normalized(vector) -> np.ndarray:
        vector = vector / vector.norm(dim=-1, keepdim=True)
        return vector.squeeze(0).detach().cpu().numpy().astype(np.float32)

    @staticmethod
    def _percentile_score(values: np.ndarray) -> np.ndarray:
        order = np.argsort(np.argsort(values, kind="stable"), kind="stable")
        return order.astype(np.float32) / max(len(values) - 1, 1)

    @staticmethod
    def _tokens(text: str) -> set[str]:
        normalized = "".join(char.lower() if char.isalnum() or "가" <= char <= "힣" else " " for char in text)
        return {token for token in normalized.split() if len(token) > 1}

    @staticmethod
    def _validate_request(match_request: MatchRequest) -> None:
        if not match_request.photo_path.is_file():
            raise LocationMatchingError("Uploaded photo is unavailable.")
        if (match_request.latitude is None) != (match_request.longitude is None):
            raise LocationMatchingError("latitude and longitude must be provided together.")
        if match_request.latitude is not None and not -90 <= match_request.latitude <= 90:
            raise LocationMatchingError("latitude must be between -90 and 90.")
        if match_request.longitude is not None and not -180 <= match_request.longitude <= 180:
            raise LocationMatchingError("longitude must be between -180 and 180.")
        if match_request.gps_accuracy_m is not None and not 0 < match_request.gps_accuracy_m <= 10_000:
            raise LocationMatchingError("gps_accuracy_m must be between 0 and 10000.")

    def _geo_score(self, asset: dict, match_request: MatchRequest) -> tuple[float | None, str]:
        location = asset.get("location") or {}
        if location.get("latitude") is None:
            return None, "기록 사진의 검증된 공간 앵커가 없어 위치 점수를 반영하지 않음"
        distance = self._haversine_m(
            match_request.latitude, match_request.longitude, location["latitude"], location["longitude"]
        )
        scale = location.get("radius_m", 200) + (match_request.gps_accuracy_m or 80)
        score = math.exp(-distance / max(scale, 1))
        return score, f"입력 좌표에서 역세권 앵커까지 약 {round(distance)}m (정확한 과거 촬영점 아님)"

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6_371_000
        lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
        value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        return 2 * radius * math.asin(math.sqrt(value))

    @staticmethod
    def _landmark_score(asset: dict, tokens: set[str]) -> tuple[float | None, str]:
        if not tokens:
            return None, "주변 장소 미입력"
        tags = HistoricalLocationMatcher._tokens(" ".join(asset.get("landmark_tags", [])))
        matched = sorted(tokens & tags)
        score = len(matched) / max(len(tokens), 1)
        if matched:
            return score, f"입력 단서와 기록 태그 일치: {', '.join(matched)}"
        return score, "입력 단서와 기록 태그의 직접 일치 없음"

    @staticmethod
    def _combine_scores(
        clip_score: float, dino_score: float, geo_score: float | None, landmark_score: float | None, gps_present: bool, landmark_present: bool
    ) -> tuple[float, dict[str, float]]:
        values = {"dino": (dino_score, 0.40), "clip": (clip_score, 0.25)}
        if gps_present and geo_score is not None:
            values["geo"] = (geo_score, 0.22)
        if landmark_present and landmark_score is not None:
            values["landmark"] = (landmark_score, 0.13)
        total_weight = sum(weight for _, weight in values.values())
        normalized = {name: score * weight / total_weight for name, (score, weight) in values.items()}
        return float(100 * sum(normalized.values())), {name: float(round(value, 4)) for name, value in normalized.items()}

    @staticmethod
    def _candidate_payload(row: dict, rank: int) -> dict:
        asset = row["asset"]
        score = row["score"]
        band = "high" if score >= 75 else "medium" if score >= 56 else "low"
        archive = {**asset["archive"], "attribution": asset["archive"].get("attribution", "서울기록원 공개 기록")}
        evidence = [
            {"label": "사진 구조", "description": f"DINOv2 구조 검색 {row['dino_rank']}위, CLIP 장면 검색 {row['clip_rank']}위"},
            {"label": "입력 위치", "description": row["geo_reason"]},
            {"label": "주변 단서", "description": row["landmark_reason"]},
            {"label": "국소 검증", "description": "현재 단계에서는 상위 후보의 국소 특징 검증을 아직 실행하지 않음"},
        ]
        return {
            "rank": rank,
            "asset_id": asset["asset_id"],
            "title": archive["title"],
            "year": archive["year"],
            "zone": asset["zone"],
            "series": asset["zone"],
            "description": asset["matching_note"],
            "short_reason": f"{row['geo_reason']} · {row['landmark_reason']}",
            "retrieval_score": float(round(score, 1)),
            "confidence_band": band,
            "verification_level": asset["verification_level"],
            "matching_note": asset["matching_note"],
            "archive": archive,
            "evidence": evidence,
            "limitations": [
                "후보 검색 점수는 동일 장소일 확률이나 역사적 사실의 증명이 아닙니다.",
                asset["matching_note"],
            ],
        }
