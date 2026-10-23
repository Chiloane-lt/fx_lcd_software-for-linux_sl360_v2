
"""Persistent configuration for fx-lcd."""

import json
import os
import tempfile
from pathlib import Path


DEFAULT_CONFIG = {
    "media_path": None,
    "mode": None,
    "rotate": 0,
    "resize": "stretch",
    "usb_vid": 0x2000,
    "usb_pid": 0x3002,
}

VALID_MODES = {"image", "gif", "video"}
VALID_ROTATIONS = {0, 90, 180, 270}
VALID_RESIZE_MODES = {"stretch", "fit", "crop"}
VALID_CONFIG_KEYS = set(DEFAULT_CONFIG)

def validate_usb_id(value, name):
    """Validate a USB vendor or product ID."""
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError(
            f"Invalid fx-lcd configuration: '{name}' must be "
            "an integer between 0 and 65535 (0xFFFF)."
        )

def get_config_path():
    """Return the path to the user's fx-lcd configuration file."""
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser()

    return config_home / "fx-lcd" / "config.json"


def validate_config(config):
    """Validate configuration fields, preserving defaults for missing keys."""
    if not isinstance(config, dict):
        raise ValueError("Invalid fx-lcd configuration: expected a JSON object.")

    unknown_keys = set(config) - VALID_CONFIG_KEYS
    if unknown_keys:
        names = ", ".join(sorted(str(key) for key in unknown_keys))
        raise ValueError(f"Invalid fx-lcd configuration: unknown key(s): {names}.")

    result = DEFAULT_CONFIG.copy()
    result.update(config)

    media_path = result["media_path"]
    if media_path is not None and (
        not isinstance(media_path, str) or not media_path.strip()
    ):
        raise ValueError(
            "Invalid fx-lcd configuration: 'media_path' must be null "
            "or a non-empty string."
        )

    mode = result["mode"]
    if mode is not None and mode not in VALID_MODES:
        raise ValueError(
            "Invalid fx-lcd configuration: 'mode' must be null, "
            "'image', 'gif', or 'video'."
        )

    rotate = result["rotate"]
    if type(rotate) is not int or rotate not in VALID_ROTATIONS:
        raise ValueError(
            "Invalid fx-lcd configuration: 'rotate' must be 0, 90, 180, or 270."
        )

    resize = result["resize"]
    if not isinstance(resize, str) or resize not in VALID_RESIZE_MODES:
        raise ValueError(
            "Invalid fx-lcd configuration: 'resize' must be "
            "'stretch', 'fit', or 'crop'."
        )

    validate_usb_id(result["usb_vid"], "usb_vid")
    validate_usb_id(result["usb_pid"], "usb_pid")

    return result


def load_config():
    """Load and validate configuration, defaulting missing fields."""
    config_path = get_config_path()

    if not config_path.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Cannot read fx-lcd configuration at {config_path}: {exc}"
        ) from exc

    try:
        return validate_config(config)
    except ValueError as exc:
        raise ValueError(f"Invalid configuration at {config_path}: {exc}") from exc


def save_config(config):
    """Validate and atomically save configuration as JSON."""
    config = validate_config(config)

    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=config_path.parent,
            prefix=".config-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(config, temporary_file, indent=4)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, config_path)

    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
