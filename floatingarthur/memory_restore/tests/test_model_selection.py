import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.benchmark import calculate_metrics, run_baseline_benchmark
from services.model_selection import InputProfile, select_restoration_plan


class ModelSelectionTestCase(unittest.TestCase):
    def test_resolution_policy_selects_least_aggressive_plan(self):
        self.assertEqual(select_restoration_plan(InputProfile(400, 400, 0.16)).model_name, "RealESRGAN_x4plus")
        self.assertEqual(select_restoration_plan(InputProfile(1000, 1000, 1.0)).model_name, "RealESRGAN_x2plus")
        self.assertIsNone(select_restoration_plan(InputProfile(2000, 1500, 3.0)).model_name)

    def test_metrics_and_controlled_benchmark_are_generated(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.jpg"
            Image.new("RGB", (160, 120), "#998877").save(source)
            report = run_baseline_benchmark(source, root / "benchmark")
            self.assertIn("ssim", report["metrics"])
            self.assertIn("psnr_db", report["metrics"])
            self.assertTrue((root / "benchmark" / "degraded_input.jpg").is_file())

            nearly_identical = Image.open(source).copy()
            nearly_identical.putpixel((0, 0), (154, 136, 120))
            metrics = calculate_metrics(Image.open(source), nearly_identical)
            self.assertGreater(metrics["ssim"], 0.99)


if __name__ == "__main__":
    unittest.main()
