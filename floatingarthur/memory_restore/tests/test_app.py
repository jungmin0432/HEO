import unittest
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from app import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory()
        app = create_app()
        app.config.update(OUTPUT_ROOT=self.tempdir.name, UPLOAD_ROOT=self.tempdir.name)
        self.client = app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_home_returns_foundation_status(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["stage"], "foundation")

    def test_places_include_match_status(self):
        response = self.client.get("/api/v1/places")
        self.assertEqual(response.status_code, 200)
        places = response.get_json()["places"]
        self.assertGreaterEqual(len(places), 3)
        self.assertTrue(all(place["matching_status"] in {"EXACT", "NEARBY", "REFERENCE"} for place in places))

    def test_health_describes_local_api_without_exposing_metrics(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["bind_scope"], "local_only")
        self.assertNotIn("psnr", payload)
        self.assertNotIn("ssim", payload)

    def test_location_matching_status_exposes_cache_scope_without_loading_a_model(self):
        response = self.client.get("/api/v1/location-matching/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["asset_count"], 56)
        self.assertEqual(payload["anchored_asset_count"], 56)
        self.assertEqual(payload["coordinate_policy"], "station_area_anchor_only")

    def test_location_match_requires_a_photo(self):
        response = self.client.post("/api/v1/location-matches", data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("photo is required", response.get_json()["error"])

    def test_prototype_ui_is_separate_from_api_root(self):
        response = self.client.get("/prototype")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AI Time Studio", response.data)
        response.close()

        stylesheet = self.client.get("/prototype/assets/styles.css")
        script = self.client.get("/prototype/assets/app.js")
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(script.status_code, 200)
        stylesheet.close()
        script.close()

    def test_api_allows_separate_frontend_during_development(self):
        response = self.client.get("/api/v1/places")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_upload_creates_traceable_baseline_record_and_asset_urls(self):
        image_bytes = BytesIO()
        Image.new("RGB", (80, 60), "white").save(image_bytes, "JPEG")
        image_bytes.seek(0)

        response = self.client.post(
            "/api/v1/restorations",
            data={"photo": (image_bytes, "demo.jpg"), "use_ai": "false"},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["source_type"], "user_upload")
        self.assertEqual(payload["ai_status"], "not_requested")
        self.assertIn("preserve", payload["assets"])
        self.assertIn("preserve", payload["downloads"])
        self.assertGreaterEqual(len(payload["explanations"]), 3)
        detail_response = self.client.get(payload["detail_url"])
        asset_response = self.client.get(payload["assets"]["conservative"])
        download_response = self.client.get(payload["downloads"]["preserve"])
        explanation_response = self.client.get(payload["explanation_url"])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(download_response.status_code, 200)
        self.assertIn("attachment", download_response.headers["Content-Disposition"])
        self.assertEqual(explanation_response.status_code, 200)
        self.assertGreaterEqual(len(explanation_response.get_json()["explanations"]), 3)
        detail_response.close()
        asset_response.close()
        download_response.close()
        explanation_response.close()

    def test_png_upload_preserves_png_original_asset(self):
        image_bytes = BytesIO()
        Image.new("RGBA", (48, 48), (20, 129, 138, 255)).save(image_bytes, "PNG")
        image_bytes.seek(0)

        response = self.client.post(
            "/api/v1/restorations",
            data={"photo": (image_bytes, "demo.png"), "use_ai": "false"},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["variants"]["preserve"]["file"].endswith(".png"))
        asset_response = self.client.get(payload["assets"]["preserve"])
        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(asset_response.mimetype, "image/png")
        asset_response.close()

    def test_archive_restoration_links_output_to_selected_historical_record(self):
        response = self.client.post(
            "/api/v1/restorations",
            data={
                "source_mode": "archive",
                "place_id": "euljiro-line2-opening-1983-corridor",
                "use_ai": "false",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["source_type"], "archive_reference")
        self.assertEqual(payload["historical_context"]["year"], 1983)
        self.assertIn("archive", payload["historical_context"])
        self.assertIn("asset_url", payload["historical_context"])

    def test_upload_can_keep_a_selected_archive_candidate_as_historical_context(self):
        archive_index = Path(__file__).resolve().parents[1] / "data" / "archive_index.json"
        matched_asset_id = json.loads(archive_index.read_text(encoding="utf-8"))["assets"][0]["asset_id"]
        image_bytes = BytesIO()
        Image.new("RGB", (40, 40), "white").save(image_bytes, "JPEG")
        image_bytes.seek(0)

        response = self.client.post(
            "/api/v1/restorations",
            data={
                "photo": (image_bytes, "current.jpg"),
                "matched_asset_id": matched_asset_id,
                "use_ai": "false",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        context = response.get_json()["historical_context"]
        self.assertEqual(context["asset_id"], matched_asset_id)
        self.assertIn("/assets/archive/", context["asset_url"])


if __name__ == "__main__":
    unittest.main()
