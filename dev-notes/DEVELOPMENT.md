# FX LCD Linux Driver — Development Notes

## Current test hardware
- Cooler: ID-COOLING SL360 V2
- USB VID:PID: 2000:3002
- USB product: HOTSPOTEKUSB HID DEMO
- Display resolution observed: 480x480
- OS: Fedora 44
- Python environment: project-local .venv
- Python dependency: hidapi; Pillow

## Current working changes
- core.py: uses VID 0x2000 and PID 0x3002.
- core.py: send_commands() sends LIG brightness command but skips DIS.
- image.py: resizes images to 480x480 and encodes baseline JPEG.
- main.py: original CLI interface retained, including --mode and --rotate.

## Confirmed behaviour
- The test image displays correctly at 480x480.
- Continuous image streaming keeps the image visible.
- With the HID connection open and streaming stopped, the image remained visible during the 25-second idle test.
- After the HID connection closes, the display shuts down after approximately 2–3 seconds.
- Skipping DIS prevented the built-in default text screen from reappearing in the observed tests.

## Protocol notes
- Frame header begins with CRT and DRA markers.
- JPEG payload is sent in 1024-byte chunks, prefixed with report ID 0x00.
- Inter-chunk delay is approximately 3 ms.
- LIG brightness command uses brightness byte 0x64.
- The exact reason the display shuts down when the HID connection closes remains unconfirmed.

## Development rules
- Test changes locally before committing.
- Keep the working 480x480 image path and no-DIS behaviour unless a test shows a better result.
- Do not package for installation until explicitly requested.
- Backups and test artifacts are stored in this dev-notes directory.
