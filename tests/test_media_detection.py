"""Safe media detection tests; never access the LCD or USB hardware."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from media import detect_media_type


class MediaDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def create_image(self, name="still.png"):
        path = self.root / name
        Image.new("RGB", (8, 8), color="red").save(path)
        return path

    def create_gif(self):
        path = self.root / "animated.gif"
        frames = [
            Image.new("RGB", (8, 8), color=color)
            for color in ("red", "blue")
        ]
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )
        return path

    def test_detects_still_image(self):
        path = self.create_image()

        result_path, mode = detect_media_type(str(path))

        self.assertEqual(result_path, str(path.resolve()))
        self.assertEqual(mode, "image")

    def test_detects_animated_gif(self):
        path = self.create_gif()

        result_path, mode = detect_media_type(str(path))

        self.assertEqual(result_path, str(path.resolve()))
        self.assertEqual(mode, "gif")

    def test_rejects_missing_file(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            detect_media_type(str(self.root / "missing.png"))

    def test_rejects_directory(self):
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            detect_media_type(str(self.root))

    def test_rejects_invalid_media(self):
        path = self.root / "invalid.dat"
        path.write_text("not media", encoding="utf-8")

        with patch("media.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "ffprobe is not installed"):
                detect_media_type(str(path))

    def test_rejects_image_when_video_mode_requested(self):
        path = self.create_image()

        with self.assertRaisesRegex(ValueError, "not a video"):
            detect_media_type(str(path), mode="video")

    def test_rejects_still_image_when_gif_mode_requested(self):
        path = self.create_image()

        with self.assertRaisesRegex(ValueError, "not an animated GIF"):
            detect_media_type(str(path), mode="gif")

    def test_rejects_animated_gif_when_image_mode_requested(self):
        path = self.create_gif()

        with self.assertRaisesRegex(ValueError, "use mode 'gif'"):
            detect_media_type(str(path), mode="image")

    def test_detects_video_using_mocked_ffprobe(self):
        path = self.root / "sample.mp4"
        path.write_bytes(b"mock video content")

        probe_output = json.dumps({
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 640,
                "height": 480,
            }]
        })
        completed = subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout=probe_output,
            stderr="",
        )

        with (
            patch("media.shutil.which", return_value="/usr/bin/ffprobe"),
            patch("media.subprocess.run", return_value=completed) as run,
        ):
            result_path, mode = detect_media_type(str(path))

        self.assertEqual(result_path, str(path.resolve()))
        self.assertEqual(mode, "video")
        run.assert_called_once()

    def test_rejects_video_without_video_stream(self):
        path = self.root / "audio-only.mp4"
        path.write_bytes(b"mock media content")

        completed = subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout=json.dumps({
                "streams": [{"codec_type": "audio"}]
            }),
            stderr="",
        )

        with (
            patch("media.shutil.which", return_value="/usr/bin/ffprobe"),
            patch("media.subprocess.run", return_value=completed),
        ):
            with self.assertRaisesRegex(ValueError, "No video stream"):
                detect_media_type(str(path))


if __name__ == "__main__":
    unittest.main()
