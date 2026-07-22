import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.restoration import create_baseline_restoration


class RestorationTestCase(unittest.TestCase):
    def test_creates_three_non_destructive_variants_and_record(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.jpg"
            Image.new("RGB", (80, 60), "#775544").save(source)
            before_hash = source.read_bytes()

            record = create_baseline_restoration(
                source=source,
                output_root=root / "outputs",
                source_type="personal",
                source_attribution="test",
            )
            result_dir = root / "outputs" / record["record_id"]

            self.assertEqual(source.read_bytes(), before_hash)
            self.assertEqual(record["original_sha256"], record["original_copy_sha256"])
            self.assertFalse(record["ai_marked"])
            self.assertTrue((result_dir / "conservative.jpg").is_file())
            self.assertTrue((result_dir / "expressive.jpg").is_file())
            self.assertTrue((result_dir / "restoration_record.json").is_file())


if __name__ == "__main__":
    unittest.main()
