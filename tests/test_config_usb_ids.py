"""Safe tests for fx-lcd USB ID configuration; no hardware access."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import DEFAULT_CONFIG, load_config, save_config, validate_config


class USBConfigTests(unittest.TestCase):
    def test_default_usb_ids(self):
        config = validate_config({"media_path": None})

        self.assertEqual(config["usb_vid"], 0x2000)
        self.assertEqual(config["usb_pid"], 0x3002)

    def test_usb_ids_must_be_valid_integers(self):
        for key in ("usb_vid", "usb_pid"):
            for value in (-1, 0x10000, "0x2000", True, 1.5):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValueError):
                        validate_config({key: value})

    def test_save_and_load_custom_usb_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}):
                config = DEFAULT_CONFIG.copy()
                config["usb_vid"] = 0x1234
                config["usb_pid"] = 0x5678

                save_config(config)
                loaded = load_config()

                self.assertEqual(loaded["usb_vid"], 0x1234)
                self.assertEqual(loaded["usb_pid"], 0x5678)

                config_path = Path(temp_dir) / "fx-lcd" / "config.json"
                saved_json = json.loads(config_path.read_text(encoding="utf-8"))
                self.assertEqual(saved_json["usb_vid"], 0x1234)
                self.assertEqual(saved_json["usb_pid"], 0x5678)

    def test_updating_usb_ids_preserves_media_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}):
                config = DEFAULT_CONFIG.copy()
                config.update({
                    "media_path": "/tmp/example.jpg",
                    "mode": "image",
                    "rotate": 90,
                    "resize": "fit",
                })
                save_config(config)

                config = load_config()
                config["usb_vid"] = 0x1234
                config["usb_pid"] = 0x5678
                save_config(config)

                loaded = load_config()
                self.assertEqual(loaded["media_path"], "/tmp/example.jpg")
                self.assertEqual(loaded["mode"], "image")
                self.assertEqual(loaded["rotate"], 90)
                self.assertEqual(loaded["resize"], "fit")
                self.assertEqual(loaded["usb_vid"], 0x1234)
                self.assertEqual(loaded["usb_pid"], 0x5678)


if __name__ == "__main__":
    unittest.main()
