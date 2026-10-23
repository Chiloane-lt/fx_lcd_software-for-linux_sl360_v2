"""Media type detection and basic file validation for fx-lcd."""

import shutil
import subprocess
import json

from pathlib import Path
from PIL import Image, UnidentifiedImageError


SUPPORTED_MODES = {"image", "gif", "video"}


def detect_media_type(path, mode=None):
    """Detect and validate media, optionally checking an explicit mode.

    Returns:
        A tuple of (absolute_path, detected_mode).
    """
    if mode is not None and mode not in SUPPORTED_MODES:
        raise ValueError(
            f"Unsupported media mode '{mode}'. "
            "Choose image, gif, or video."
        )

    media_path = Path(path).expanduser()

    try:
        media_path = media_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Media file does not exist: {path}") from exc

    if not media_path.is_file():
        raise ValueError(f"Media path is not a regular file: {media_path}")

    try:
        with media_path.open("rb") as media_file:
            media_file.read(1)
    except OSError as exc:
        raise ValueError(
            f"Media file is not readable: {media_path}: {exc}"
        ) from exc

    image_error = None

    try:
        with Image.open(media_path) as source:
            image_format = (source.format or "").upper()
            is_animated_gif = (
                image_format == "GIF"
                and getattr(source, "is_animated", False)
                and getattr(source, "n_frames", 1) > 1
            )

            source.load()

        detected = "gif" if is_animated_gif else "image"

        if mode == "video":
            raise ValueError(
                f"'{media_path}' is an image, not a video."
            )

        if mode == "gif" and not is_animated_gif:
            raise ValueError(
                f"'{media_path}' is not an animated GIF."
            )

        if mode == "image" and is_animated_gif:
            raise ValueError(
                f"'{media_path}' is an animated GIF; use mode 'gif'."
            )

        return str(media_path), detected

    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        image_error = exc

    if mode in ("image", "gif"):
        raise ValueError(
            f"'{media_path}' is not a valid {mode} file: {image_error}"
        ) from image_error
 
    ffprobe = shutil.which("ffprobe")

    if ffprobe is None:
        raise ValueError(
            f"Cannot identify '{media_path}' as an image or GIF, "
            "and ffprobe is not installed. Install FFmpeg to enable "
            "video detection."
        )

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries",
                "stream=codec_type,codec_name,width,height",
                "-of", "json",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(
            f"Could not inspect media file '{media_path}': {exc}"
        ) from exc

    if result.returncode != 0 or result.stderr.strip():
        detail = result.stderr.strip() or "ffprobe could not read the file."
        raise ValueError(
            f"'{media_path}' is not a supported image, GIF, "
            f"or video: {detail}"
        )

    try:
        probe_data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Could not validate media file '{media_path}': "
            "ffprobe returned invalid data."
        ) from exc

    streams = probe_data.get("streams")
    if not isinstance(streams, list):
        raise ValueError(
            f"Could not validate media file '{media_path}': "
            "ffprobe returned no valid stream list."
        )

    video_streams = [
        stream for stream in streams
        if isinstance(stream, dict)
        and stream.get("codec_type") == "video"
    ]

    if not video_streams:
        raise ValueError(
            f"'{media_path}' is not a supported image, GIF, or video: "
            "No video stream was found."
        )

    has_valid_video_stream = any(
        isinstance(stream.get("width"), int)
        and stream["width"] > 0
        and isinstance(stream.get("height"), int)
        and stream["height"] > 0
        for stream in video_streams
    )

    if not has_valid_video_stream:
        raise ValueError(
            f"'{media_path}' is not a supported video: "
            "The video stream has invalid dimensions."
        )

    if mode in ("image", "gif"):
        raise ValueError(
            f"'{media_path}' contains a video stream, not a {mode}."
        )

    return str(media_path), "video"
