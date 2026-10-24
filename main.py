#!/usr/bin/env python
import sys
import argparse
import os
import atexit
import signal
import subprocess
import time
import fcntl

from config import get_config_path, load_config, save_config
from media import detect_media_type

from image import (
    get_images_bytes,
    prepare_blob,
    get_gif_frames,
    get_video_frames,
)
from core import (
    prepare_chunks,
    send_commands,
    send_image,
    send_gif,
    send_video,
)

sys.path.append(os.path.dirname(os.path.realpath(__file__)))


# Runtime files are kept alongside the user's fx-lcd configuration.
_RUNTIME_DIR = os.path.join(os.path.dirname(get_config_path()), "runtime")
_PID_FILE = os.path.join(_RUNTIME_DIR, "fx-lcd.pid")
_LOG_FILE = os.path.join(_RUNTIME_DIR, "fx-lcd.log")
_LOCK_FILE = os.path.join(_RUNTIME_DIR, "fx-lcd.lock")


def _read_managed_pid():
    """Return the managed playback PID, or None if no valid PID is recorded."""
    try:
        with open(_PID_FILE, encoding="utf-8") as file:
            value = file.read().strip()
        pid = int(value)
        return pid if pid > 1 else None
    except (OSError, ValueError):
        return None


def _acquire_runtime_lock():
    """Acquire the exclusive lock used to coordinate start and stop."""
    os.makedirs(_RUNTIME_DIR, exist_ok=True)
    lock_file = open(_LOCK_FILE, "a", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    except BaseException:
        lock_file.close()
        raise
    return lock_file


def _remove_pid_file_if_matches(pid):
    """Remove the PID file only if it still records the supplied PID."""
    try:
        if _read_managed_pid() == pid:
            os.unlink(_PID_FILE)
    except OSError:
        pass


def _write_pid_file(pid):
    """Atomically publish the managed playback PID."""
    temporary_path = f"{_PID_FILE}.{os.getpid()}.tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            file.write(f"{pid}\n")
        os.replace(temporary_path, _PID_FILE)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def _terminate_process(process, timeout=5):
    """Terminate a child process, escalating to kill if it does not exit."""
    try:
        process.terminate()
    except OSError:
        pass

    try:
        process.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        pass

    try:
        process.kill()
    except OSError:
        pass

    try:
        process.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        return False



def _is_managed_process(pid):
    """Check that the PID belongs to an fx-lcd managed playback process."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as file:
            command = file.read().split(b"\0")

        expected_script = os.path.realpath(__file__)
        if len(command) < 2:
            return False

        actual_script = os.path.realpath(os.fsdecode(command[1]))
        if actual_script != expected_script:
            return False

        # Recognise the service during startup, before it execs playback.
        if len(command) > 2 and command[2] == b"service":
            return True

        return (
            b"--managed-playback" in command
            or b"--service-playback" in command
        )
    except (OSError, ValueError):
        return False



def _is_service_process(pid):
    """Check whether a PID belongs to service startup or playback."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as file:
            command = file.read().split(b"\0")

        expected_script = os.fsencode(os.path.realpath(__file__))
        is_fx_lcd = (
            len(command) > 1
            and os.path.realpath(os.fsdecode(command[1]))
            == os.fsdecode(expected_script)
        )

        return is_fx_lcd and (
            (len(command) > 2 and command[2] == b"service")
            or b"--service-playback" in command
        )
    except (OSError, ValueError):
        return False


def _remove_own_pid_file():
    """Remove the PID file only if it still belongs to this process."""
    try:
        if _read_managed_pid() == os.getpid():
            os.unlink(_PID_FILE)
    except OSError:
        pass


def _handle_termination(signum, frame):
    """Exit normally so playback functions can run their cleanup blocks."""
    raise SystemExit(0)


# The child playback process uses this hidden flag. A normal user playback
# invocation is unaffected.
if (sys.argv[1:2] == ["service"] or "--managed-playback" in sys.argv or "--service-playback" in sys.argv):
    signal.signal(signal.SIGTERM, _handle_termination)
    atexit.register(_remove_own_pid_file)


# Run saved playback in the foreground for systemd.
if len(sys.argv) > 1 and sys.argv[1] == "service":
    service_parser = argparse.ArgumentParser(
        prog="fx-lcd service",
        description="Run saved playback in the foreground for systemd.",
    )
    service_parser.add_argument(
        "--debug-timing",
        action="store_true",
        help="Print GIF/video frame transmission timing for debugging.",
    )
    service_parser.add_argument(
        "--chunk-delay",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="Delay between GIF/video USB chunks in seconds (default: 0.0).",
    )
    service_args = service_parser.parse_args(sys.argv[2:])

    if service_args.chunk_delay < 0:
        service_parser.error("--chunk-delay must be zero or greater.")

    try:
        config = load_config()
    except (OSError, ValueError, TypeError) as exc:
        service_parser.error(f"Cannot load configuration: {exc}")

    media_path = config.get("media_path")
    mode = config.get("mode")
    rotate = config.get("rotate")
    resize = config.get("resize")

    if not isinstance(media_path, str) or not media_path.strip():
        service_parser.error(
            "No media file is configured. Choose one with "
            "'fx-lcd set-media PATH'."
        )
    if mode not in ("image", "gif", "video"):
        service_parser.error(f"Invalid saved media type: {mode!r}.")
    if type(rotate) is not int or rotate not in (0, 90, 180, 270):
        service_parser.error(f"Invalid saved rotation: {rotate!r}.")
    if resize not in ("stretch", "fit", "crop"):
        service_parser.error(f"Invalid saved resize mode: {resize!r}.")

    try:
        media_path, detected_mode = detect_media_type(media_path, mode=mode)
    except (OSError, ValueError, TypeError) as exc:
        service_parser.error(f"Invalid configured media file: {exc}")

    runtime_lock = _acquire_runtime_lock()
    current_pid = _read_managed_pid()

    if current_pid is not None and _is_managed_process(current_pid):
        runtime_lock.close()
        service_parser.error(
            f"fx-lcd is already running (PID {current_pid}). "
            "Stop the existing playback before starting the service."
        )

    if current_pid is not None:
        _remove_pid_file_if_matches(current_pid)

    os.makedirs(_RUNTIME_DIR, exist_ok=True)
    _write_pid_file(os.getpid())

    child_args = [
        sys.executable,
        os.path.realpath(__file__),
        "--mode", detected_mode,
        media_path,
        "--rotate", str(rotate),
        "--resize", resize,
        "--chunk-delay", str(service_args.chunk_delay),
        "--service-playback",
    ]
    if service_args.debug_timing:
        child_args.append("--debug-timing")

    # Release the lock before exec; systemd will track this same PID.
    runtime_lock.close()
    try:
        os.execv(sys.executable, child_args)
    except OSError as exc:
        _remove_pid_file_if_matches(os.getpid())
        service_parser.error(f"Could not launch service playback: {exc}")


# Handle stop before parsing the normal playback arguments.
if len(sys.argv) > 1 and sys.argv[1] == "stop":
    stop_parser = argparse.ArgumentParser(
        prog="fx-lcd stop",
        description="Stop managed background playback.",
    )
    stop_parser.parse_args(sys.argv[2:])

    runtime_lock = _acquire_runtime_lock()
    pid = _read_managed_pid()
    if pid is None:
        print("fx-lcd is not running (no valid PID file).")
        sys.exit(0)

    if not _is_managed_process(pid):
        _remove_pid_file_if_matches(pid)
        print("No managed fx-lcd playback process is running.")
        sys.exit(0)

    if _is_service_process(pid):
        print(
            "fx-lcd is managed by systemd; use "
            "'sudo systemctl stop fx-lcd.service'."
        )
        sys.exit(2)

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _remove_pid_file_if_matches(pid)
        print("fx-lcd is not running.")
        sys.exit(0)
    except PermissionError:
        stop_parser.error(f"Permission denied when stopping fx-lcd PID {pid}.")

    # Allow the playback process to close its USB device and remove its PID file.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not _is_managed_process(pid):
            break
        time.sleep(0.1)

    if _is_managed_process(pid):
        print(
            f"Stop requested for fx-lcd (PID {pid}); "
            "the process has not exited yet. Check the log before retrying."
        )
    else:
        print("fx-lcd stopped. The LCD should switch off after its timeout.")
    sys.exit(0)




# Handle set-media separately so it cannot interfere with playback arguments.
if len(sys.argv) > 1 and sys.argv[1] == "set-media":
    set_media_parser = argparse.ArgumentParser(
        prog="fx-lcd set-media",
        description="Choose and save the media file for fx-lcd.",
    )
    set_media_parser.add_argument(
        "media_path",
        help="Path to an image, GIF, or video.",
    )
    set_media_parser.add_argument(
        "--mode",
        choices=["image", "gif", "video"],
        help="Optionally specify the media type instead of detecting it.",
    )
    set_media_parser.add_argument(
        "--rotate",
        type=int,
        choices=[0, 90, 180, 270],
        help="Clockwise rotation (default: preserve saved value, or 0).",
    )
    set_media_parser.add_argument(
        "--resize",
        choices=["stretch", "fit", "crop"],
        help="Resizing mode (default: preserve saved value, or stretch).",
    )

    set_media_args = set_media_parser.parse_args(sys.argv[2:])

    try:
        # Validate the media before changing the saved configuration.
        media_path, media_mode = detect_media_type(
            set_media_args.media_path,
            mode=set_media_args.mode,
        )

        # Load existing settings, or defaults if no configuration exists.
        config = load_config()

        # Always update the selected media.
        config["media_path"] = media_path
        config["mode"] = media_mode

        # Preserve existing settings when options are omitted.
        if set_media_args.rotate is not None:
            config["rotate"] = set_media_args.rotate

        if set_media_args.resize is not None:
            config["resize"] = set_media_args.resize

        save_config(config)

    except (OSError, ValueError, TypeError) as exc:
        set_media_parser.error(str(exc))

    print(f"Saved media: {media_path}")
    print(f"Media type: {media_mode}")
    print(f"Rotation: {config['rotate']}")
    print(f"Resize: {config['resize']}")
    print(f"Configuration: {get_config_path()}")
    sys.exit(0)


# Configure USB IDs without connecting to the LCD.
if len(sys.argv) > 1 and sys.argv[1] == "set-device":
    device_parser = argparse.ArgumentParser(
        prog="fx-lcd set-device",
        description="Save the USB vendor and product IDs for fx-lcd.",
    )
    device_parser.add_argument(
        "vid",
        type=lambda value: int(value, 0),
        help="USB vendor ID, e.g. 0x2000.",
    )
    device_parser.add_argument(
        "pid",
        type=lambda value: int(value, 0),
        help="USB product ID, e.g. 0x3002.",
    )
    device_args = device_parser.parse_args(sys.argv[2:])

    try:
        config = load_config()
        config["usb_vid"] = device_args.vid
        config["usb_pid"] = device_args.pid
        save_config(config)
    except (OSError, ValueError, TypeError) as exc:
        device_parser.error(str(exc))

    print(f"USB vendor ID:  0x{config['usb_vid']:04X}")
    print(f"USB product ID: 0x{config['usb_pid']:04X}")
    print(f"Configuration: {get_config_path()}")
    sys.exit(0)


# Handle status separately; this command never connects to the LCD.
if len(sys.argv) > 1 and sys.argv[1] == "status":
    status_parser = argparse.ArgumentParser(
        prog="fx-lcd status",
        description="Show the saved fx-lcd configuration.",
    )
    status_parser.parse_args(sys.argv[2:])

    try:
        config = load_config()
    except (OSError, ValueError, TypeError) as exc:
        status_parser.error(f"Cannot load configuration: {exc}")

    print(f"Configuration: {get_config_path()}")

    media_path = config["media_path"]
    if media_path is None:
        print("Saved media: None (not configured)")
    else:
        print(f"Saved media: {media_path}")
        print(f"Media type: {config['mode']}")

        if os.path.isfile(media_path):
            print("File status: exists")
        else:
            print("File status: missing")

    print(f"Rotation: {config['rotate']}")
    print(f"Resize: {config['resize']}")
    sys.exit(0)


# Handle start using the saved configuration.
if len(sys.argv) > 1 and sys.argv[1] == "start":
    start_parser = argparse.ArgumentParser(
        prog="fx-lcd start",
        description="Start playback using the saved configuration.",
    )

    start_parser.add_argument(
        "--debug-timing",
        action="store_true",
        help="Print GIF/video frame transmission timing for debugging.",
    )
    start_parser.add_argument(
        "--chunk-delay",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="Delay between GIF/video USB chunks in seconds (default: 0.0).",
    )
    start_args = start_parser.parse_args(sys.argv[2:])

    if start_args.chunk_delay < 0:
        start_parser.error("--chunk-delay must be zero or greater.")

    try:
        config = load_config()
    except (OSError, ValueError, TypeError) as exc:
        start_parser.error(f"Cannot load configuration: {exc}")

    media_path = config.get("media_path")
    mode = config.get("mode")
    rotate = config.get("rotate")
    resize = config.get("resize")

    # A media file must be selected before playback can start.
    if not isinstance(media_path, str) or not media_path.strip():
        start_parser.error(
            "No media file is configured. Choose one with "
            "'fx-lcd set-media PATH'."
        )

    # Validate the saved playback settings instead of silently
    # replacing invalid values with defaults.
    if mode not in ("image", "gif", "video"):
        start_parser.error(
            f"Invalid saved media type: {mode!r}. "
            "Choose a media file again with 'fx-lcd set-media PATH'."
        )

    if type(rotate) is not int or rotate not in (0, 90, 180, 270):
        start_parser.error(
            f"Invalid saved rotation: {rotate!r}. "
            "Set it with 'fx-lcd set-media PATH --rotate 0|90|180|270'."
        )

    if resize not in ("stretch", "fit", "crop"):
        start_parser.error(
            f"Invalid saved resize mode: {resize!r}. "
            "Set it with 'fx-lcd set-media PATH --resize stretch|fit|crop'."
        )

    try:
        # Check that the file exists, is usable, and matches its
        # saved media type. This does not send anything to the LCD.
        media_path, detected_mode = detect_media_type(
            media_path,
            mode=mode,
        )
    except (OSError, ValueError, TypeError) as exc:
        start_parser.error(f"Invalid configured media file: {exc}")

    runtime_lock = _acquire_runtime_lock()

    # Do not launch a second managed playback process.
    current_pid = _read_managed_pid()
    if current_pid is not None and _is_managed_process(current_pid):
        start_parser.error(
            f"fx-lcd is already running (PID {current_pid}). "
            "Use 'fx-lcd stop' before starting it again."
        )

    os.makedirs(_RUNTIME_DIR, exist_ok=True)

    child_args = [
        sys.executable,
        os.path.realpath(__file__),
        "--mode", detected_mode,
        media_path,
        "--rotate", str(rotate),
        "--resize", resize,
        "--chunk-delay", str(start_args.chunk_delay),
        "--managed-playback",
    ]
    if start_args.debug_timing:
        child_args.append("--debug-timing")

    process = None
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as log:
            process = subprocess.Popen(
                child_args,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
            _write_pid_file(process.pid)
    except OSError as exc:
        if process is not None:
            _terminate_process(process)
            _remove_pid_file_if_matches(process.pid)

        start_parser.error(f"Could not start playback: {exc}")

    # Confirm the child is still running after launch.
    time.sleep(0.2)
    if process.poll() is not None:
        _remove_pid_file_if_matches(process.pid)
        start_parser.error(
            f"Playback exited during startup. See log: {_LOG_FILE}"
        )

    print(f"fx-lcd started (PID {process.pid}).")
    print(f"Log: {_LOG_FILE}")
    runtime_lock.close()
    sys.exit(0)

parser = argparse.ArgumentParser(
    prog="fx-lcd",
    description="Display images, GIFs, and videos on the LCD.",
)
parser.add_argument(
    "--mode",
    choices=["image", "gif", "video"],
    required=True,
    help="Playback mode: image, gif, or video.",
)
parser.add_argument("path", help="Path to the media file to play.")
parser.add_argument(
    "--rotate",
    type=int,
    default=0,
    choices=[0, 90, 180, 270],
    help="Clockwise rotation.",
)
parser.add_argument(
    "--resize",
    choices=["stretch", "fit", "crop"],
    default="stretch",
    help="Resizing mode: stretch, fit (black background), or crop.",
)
parser.add_argument(
    "--debug-timing",
    action="store_true",
    help="Print GIF/video frame transmission timing for debugging.",
)
parser.add_argument(
    "--chunk-delay",
    type=float,
    default=0.0,
    metavar="SECONDS",
    help="Delay between GIF/video USB chunks in seconds (default: 0.0).",
)
parser.add_argument(
    "--managed-playback",
    action="store_true",
    help=argparse.SUPPRESS,
)
parser.add_argument(
    "--service-playback",
    action="store_true",
    help=argparse.SUPPRESS,
)

args = parser.parse_args()

if not os.path.isfile(args.path):
    parser.error(f"file dont exests: {args.path}")

if args.mode == 'image':
    try:
        images_bytes = get_images_bytes(
            args.path,
            rotate=args.rotate,
            resize_mode=args.resize,
        )
        blob = prepare_blob(images_bytes)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    chunks = prepare_chunks(blob)
    send_commands()
    send_image(chunks)

elif args.mode == 'gif':
    try:
        frames = [
            (prepare_chunks(prepare_blob(jpeg_bytes)), duration_ms)
            for jpeg_bytes, duration_ms in get_gif_frames(
                args.path,
                rotate=args.rotate,
                resize_mode=args.resize,
            )
        ]

        if not frames:
            parser.error("The GIF contains no frames.")

    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    send_commands()
    send_gif(
        frames,
        debug_timing=args.debug_timing,
        chunk_delay=args.chunk_delay,
    )

else:
    try:
        send_commands()
        send_video(
            lambda: get_video_frames(
                args.path,
                rotate=args.rotate,
                resize_mode=args.resize,
            ),
            debug_timing=args.debug_timing,
            chunk_delay=args.chunk_delay,
        )
    except KeyboardInterrupt:
        print("\nVideo playback stopped.")
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
