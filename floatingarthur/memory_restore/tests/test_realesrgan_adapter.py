import os
import unittest
from unittest.mock import patch

from services.realesrgan_adapter import AIBackendUnavailable, RealESRGANSettings, run_realesrgan


class RealESRGANAdapterTestCase(unittest.TestCase):
    def test_default_settings_do_not_claim_a_configured_runner(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = RealESRGANSettings.from_environment()
        self.assertEqual(settings.command_template, "")
        self.assertEqual(settings.model_name, "RealESRGAN_x4plus")

    def test_runner_requires_explicit_server_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AIBackendUnavailable):
                run_realesrgan(__file__, __file__ + ".out")

    def test_local_worker_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {"ENABLE_LOCAL_REALESRGAN": "1"}, clear=True):
            settings = RealESRGANSettings.from_environment()
        self.assertTrue(settings.use_local_worker)


if __name__ == "__main__":
    unittest.main()
