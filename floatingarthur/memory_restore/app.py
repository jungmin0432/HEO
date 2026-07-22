from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, jsonify, request, send_file, send_from_directory, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from services.realesrgan_adapter import RealESRGANSettings
from services.restoration import build_change_explanations, create_upload_restoration
from services.location_matching import HistoricalLocationMatcher, LocationMatchingError, MatchRequest


PROJECT_ROOT = Path(__file__).resolve().parent
PHOTO_ROOT = PROJECT_ROOT.parent / "photos"
PLACE_DATA_FILE = PROJECT_ROOT / "data" / "places.json"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"
UPLOAD_ROOT = PROJECT_ROOT / "uploads"
UI_PROTOTYPE_ROOT = PROJECT_ROOT / "ui_prototype"
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
RECORD_ID_PATTERN = re.compile(r"^baseline-\d{8}T\d{6}Z-[a-f0-9]{8}$")


def load_places() -> list[dict]:
    with PLACE_DATA_FILE.open(encoding="utf-8") as file:
        return json.load(file)["places"]


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024
    app.config["OUTPUT_ROOT"] = OUTPUT_ROOT
    app.config["UPLOAD_ROOT"] = UPLOAD_ROOT
    location_matcher = HistoricalLocationMatcher(PROJECT_ROOT)

    @app.after_request
    def add_development_cors(response):
        # The separate responsive frontend can call this prototype during local demos.
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.get("/")
    def index():
        return {
            "service": "을지로 기억복원소",
            "stage": "foundation",
            "message": "장소 카드와 복원 기록 구조를 준비했습니다.",
            "next": "AI 복원 파이프라인과 사용자 화면은 다음 단계에서 추가합니다.",
        }

    @app.get("/api/v1/health")
    def health():
        settings = RealESRGANSettings.from_environment()
        return jsonify(
            {
                "status": "ok",
                "api_version": "v1",
                "ai_mode": "enabled" if settings.command_template or settings.use_local_worker else "baseline_only",
                "bind_scope": "local_only",
                "location_matching": location_matcher.status(),
            }
        )

    @app.get("/api/v1/location-matching/status")
    def location_matching_status():
        return jsonify(location_matcher.status())

    @app.get("/prototype")
    def ui_prototype():
        return send_from_directory(UI_PROTOTYPE_ROOT, "index.html")

    @app.get("/prototype/assets/<path:asset_name>")
    def ui_prototype_asset(asset_name: str):
        return send_from_directory(UI_PROTOTYPE_ROOT / "assets", asset_name)

    @app.get("/api/v1/places")
    @app.get("/api/places")
    def places():
        return jsonify({"places": load_places()})

    @app.get("/api/v1/places/<place_id>")
    @app.get("/api/places/<place_id>")
    def place_detail(place_id: str):
        place = next((item for item in load_places() if item["id"] == place_id), None)
        if not place:
            abort(404)
        return jsonify(place)

    @app.get("/api/v1/restorations")
    @app.get("/api/restorations")
    def restoration_records():
        records = []
        output_root = Path(app.config["OUTPUT_ROOT"])
        if output_root.exists():
            for record_file in sorted(output_root.glob("*/restoration_record.json"), reverse=True):
                with record_file.open(encoding="utf-8") as file:
                    records.append(json.load(file))
        return jsonify({"records": [restoration_payload(record) for record in records]})

    @app.get("/assets/history/<place_id>")
    def history_asset(place_id: str):
        place = next((item for item in load_places() if item["id"] == place_id), None)
        if not place:
            abort(404)

        asset_path = PHOTO_ROOT / place["historical_asset_path"]
        if not asset_path.is_file():
            abort(404)
        return send_file(asset_path, conditional=True)

    @app.get("/assets/archive/<path:asset_id>")
    def archive_asset(asset_id: str):
        asset = next((item for item in location_matcher.assets if item["asset_id"] == asset_id), None)
        if not asset:
            abort(404)
        asset_path = PHOTO_ROOT / "history_photo" / asset["relative_path"]
        if not asset_path.is_file():
            abort(404)
        return send_file(asset_path, conditional=True)

    @app.post("/api/v1/location-matches")
    def location_matches():
        uploaded = request.files.get("photo")
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": "photo is required as multipart/form-data"}), 400
        suffix = Path(secure_filename(uploaded.filename)).suffix.lower()
        if suffix not in ALLOWED_IMAGE_SUFFIXES:
            return jsonify({"error": "photo must be JPG, PNG, or WebP"}), 400

        try:
            latitude = optional_float(request.form.get("latitude"), "latitude")
            longitude = optional_float(request.form.get("longitude"), "longitude")
            gps_accuracy_m = optional_float(request.form.get("gps_accuracy_m"), "gps_accuracy_m")
            limit = int(request.form.get("limit", "5"))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        if not 1 <= limit <= 10:
            return jsonify({"error": "limit must be between 1 and 10"}), 400

        upload_root = Path(app.config["UPLOAD_ROOT"])
        upload_root.mkdir(parents=True, exist_ok=True)
        upload_path = upload_root / f"match-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}{suffix}"
        uploaded.save(upload_path)
        try:
            with Image.open(upload_path) as image:
                image.verify()
            result = location_matcher.find_candidates(
                MatchRequest(
                    photo_path=upload_path,
                    latitude=latitude,
                    longitude=longitude,
                    gps_accuracy_m=gps_accuracy_m,
                    landmark_text=request.form.get("landmark_text", "").strip(),
                    limit=limit,
                )
            )
        except (UnidentifiedImageError, OSError):
            return jsonify({"error": "photo could not be opened as an image"}), 400
        except LocationMatchingError as error:
            return jsonify({"error": str(error)}), 503
        finally:
            upload_path.unlink(missing_ok=True)

        for candidate in result["candidates"]:
            candidate["asset_url"] = url_for("archive_asset", asset_id=candidate["asset_id"], _external=False)
        return jsonify(result)

    @app.post("/api/v1/restorations")
    def create_restoration():
        source_mode = request.form.get("source_mode", "upload")
        if source_mode not in {"upload", "archive"}:
            return jsonify({"error": "source_mode must be upload or archive"}), 400
        place_id = request.form.get("place_id") or None
        place = next((item for item in load_places() if item["id"] == place_id), None)
        if place_id and place is None:
            return jsonify({"error": "unknown place_id"}), 400
        if source_mode == "archive" and place is None:
            return jsonify({"error": "place_id is required when source_mode is archive"}), 400

        requested_ai = request.form.get("use_ai", "true").lower() in {"1", "true", "yes"}
        historical_context = historical_context_payload(place) if place else None
        matched_asset_id = request.form.get("matched_asset_id") or None
        if matched_asset_id:
            matched_asset = next((item for item in location_matcher.assets if item["asset_id"] == matched_asset_id), None)
            if matched_asset is None:
                return jsonify({"error": "unknown matched_asset_id"}), 400
            if historical_context is None:
                historical_context = archive_context_payload(matched_asset)
        upload_path: Path | None = None
        delete_after_processing = False

        if source_mode == "archive":
            source_path = PHOTO_ROOT / place["historical_asset_path"]
            source_attribution = place["archive"]["attribution"]
            source_type = "archive_reference"
        else:
            uploaded = request.files.get("photo")
            if uploaded is None or not uploaded.filename:
                return jsonify({"error": "photo is required as multipart/form-data"}), 400
            suffix = Path(secure_filename(uploaded.filename)).suffix.lower()
            if suffix not in ALLOWED_IMAGE_SUFFIXES:
                return jsonify({"error": "photo must be JPG, PNG, or WebP"}), 400
            upload_root = Path(app.config["UPLOAD_ROOT"])
            upload_root.mkdir(parents=True, exist_ok=True)
            upload_name = f"upload-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}{suffix}"
            upload_path = upload_root / upload_name
            uploaded.save(upload_path)
            source_path = upload_path
            source_attribution = request.form.get("source_attribution", "User-provided local demo photo")
            source_type = "user_upload"
            delete_after_processing = True

        try:
            with Image.open(source_path) as image:
                image.verify()
            record = create_upload_restoration(
                source=source_path,
                output_root=Path(app.config["OUTPUT_ROOT"]),
                source_attribution=source_attribution,
                place_id=place_id,
                request_ai=requested_ai,
                source_type=source_type,
                historical_context=historical_context,
            )
        except (UnidentifiedImageError, OSError):
            if upload_path:
                upload_path.unlink(missing_ok=True)
            return jsonify({"error": "photo could not be opened as an image"}), 400
        finally:
            if delete_after_processing and upload_path:
                upload_path.unlink(missing_ok=True)

        return jsonify(restoration_payload(record)), 201

    @app.get("/api/v1/restorations/<record_id>")
    def restoration_detail(record_id: str):
        record = load_record(app, record_id)
        if record is None:
            abort(404)
        return jsonify(restoration_payload(record))

    @app.get("/api/v1/restorations/<record_id>/assets/<variant_id>")
    def restoration_asset(record_id: str, variant_id: str):
        record = load_record(app, record_id)
        if record is None or variant_id not in record["variants"]:
            abort(404)
        asset_path = Path(app.config["OUTPUT_ROOT"]) / record_id / record["variants"][variant_id]["file"]
        if not asset_path.is_file():
            abort(404)
        return send_file(asset_path, conditional=True)

    @app.get("/api/v1/restorations/<record_id>/downloads/<variant_id>")
    def restoration_download(record_id: str, variant_id: str):
        record = load_record(app, record_id)
        if record is None or variant_id not in record["variants"]:
            abort(404)
        source_name = record["variants"][variant_id]["file"]
        asset_path = Path(app.config["OUTPUT_ROOT"]) / record_id / source_name
        if not asset_path.is_file():
            abort(404)
        download_name = f"{record_id}-{variant_id}{asset_path.suffix.lower()}"
        return send_file(asset_path, as_attachment=True, download_name=download_name, conditional=True)

    @app.get("/api/v1/restorations/<record_id>/explanation")
    def restoration_explanation(record_id: str):
        record = load_record(app, record_id)
        if record is None:
            abort(404)
        return jsonify(
            {
                "record_id": record_id,
                "input_resolution": record.get("input_resolution"),
                "restoration_plan": record.get("restoration_plan"),
                "explanations": record.get("change_explanations") or build_change_explanations(record),
                "warnings": record.get("warnings", []),
            }
        )

    return app


def load_record(app: Flask, record_id: str) -> dict | None:
    if not RECORD_ID_PATTERN.fullmatch(record_id):
        return None
    record_file = Path(app.config["OUTPUT_ROOT"]) / record_id / "restoration_record.json"
    if not record_file.is_file():
        return None
    with record_file.open(encoding="utf-8") as file:
        return json.load(file)


def restoration_payload(record: dict) -> dict:
    payload = dict(record)
    record_id = record["record_id"]
    payload["assets"] = {
        variant_id: url_for("restoration_asset", record_id=record_id, variant_id=variant_id, _external=False)
        for variant_id in record["variants"]
    }
    payload["downloads"] = {
        variant_id: url_for("restoration_download", record_id=record_id, variant_id=variant_id, _external=False)
        for variant_id in record["variants"]
    }
    payload["explanations"] = record.get("change_explanations") or build_change_explanations(record)
    payload["detail_url"] = url_for("restoration_detail", record_id=record_id, _external=False)
    payload["explanation_url"] = url_for("restoration_explanation", record_id=record_id, _external=False)
    if record.get("historical_context"):
        payload["historical_context"] = dict(record["historical_context"])
        if record["historical_context"].get("place_id"):
            payload["historical_context"]["asset_url"] = url_for(
                "history_asset", place_id=record["historical_context"]["place_id"], _external=False
            )
        elif record["historical_context"].get("asset_id"):
            payload["historical_context"]["asset_url"] = url_for(
                "archive_asset", asset_id=record["historical_context"]["asset_id"], _external=False
            )
    return payload


def historical_context_payload(place: dict) -> dict:
    return {
        "place_id": place["id"],
        "title": place["title"],
        "year": place["year"],
        "matching_status": place["matching_status"],
        "matching_note": place["matching_note"],
        "archive": place["archive"],
    }


def archive_context_payload(asset: dict) -> dict:
    return {
        "asset_id": asset["asset_id"],
        "title": asset["archive"]["title"],
        "year": asset["archive"]["year"],
        "matching_status": asset["verification_level"],
        "matching_note": asset["matching_note"],
        "archive": asset["archive"],
    }


def optional_float(value: str | None, field_name: str) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a number") from error


if __name__ == "__main__":
    create_app().run(debug=True)
