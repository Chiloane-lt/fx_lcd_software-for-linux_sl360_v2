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
- image.py: starts at JPEG quality 80 and retries in steps of 5 down to quality 20 if the payload exceeds 65,503 bytes.
- image.py: validates the complete frame size against the 65,535-byte limit, including the 32-byte header.
- main.py: original CLI interface retained, including --mode and --rotate; image-preparation errors are reported cleanly without a traceback.

## Confirmed behaviour
- The test image displays correctly at 480x480.
- Continuous image streaming keeps the image visible.
- With the HID connection open and streaming stopped, the image remained visible during the 25-second idle test.
- After the HID connection closes, the display shuts down after approximately 2–3 seconds.
- Skipping DIS prevented the built-in default text screen from reappearing in the observed tests.
- A 70,155-byte JPEG at quality 80 was successfully recompressed at quality 75 to 61,624 bytes and displayed correctly.
- When compression cannot fit within the configured limit, all quality levels from 80 through 20 are tried and a clear error is raised.
- main.py reports image-preparation failures through argparse and exits with status 2 before sending data to the LCD.

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

## GIF and future animation support

### Current direction
- Add GIF support through a new CLI mode, keeping the existing image mode working.
- Example command:
  `python main.py --mode gif animation.gif`
- Use Pillow (PIL), which is already available in the project environment, for the initial GIF implementation.
- Extract GIF frames and their duration metadata.
- Handle frame compositing and transparency so each LCD frame represents the complete image.
- Reuse the existing image processing pipeline for rotation, resizing to 480x480, RGB conversion, and JPEG encoding.
- Send animation frames through the existing HID streaming implementation.
- Keep the HID connection open during animation playback.

### Media processing architecture
The planned architecture separates media decoding from LCD communication:

1. CLI: accepts image, GIF, and future video modes.
2. Media reader: extracts frames and timing information from the selected format.
3. Image processing: handles compositing, rotation, resizing, and RGB conversion.
4. JPEG encoding: converts processed frames into the format used by the LCD protocol.
5. LCD streaming: sends encoded frames through the existing HID communication code.

This separation should allow additional media formats to be supported without rewriting the LCD protocol implementation.

### Library considerations
- Pillow is the preferred starting point for GIF support because it is already installed and provides frame extraction, duration metadata, image transformations, and JPEG encoding.
- imageio is a possible future dependency for broader media-reader support, particularly video formats and plugin-based decoding.
- imageio is not required for the initial GIF implementation.
- Any future imageio integration should preserve the separation between media reading, image processing, and HID communication.

### GIF implementation considerations
- Read each frame and its duration.
- Respect frame compositing and transparency.
- Convert frames into complete 480x480 RGB images.
- Reuse existing JPEG encoding and HID framing.
- Preserve the current static image CLI behaviour.
- Test playback on the actual SL360 V2 display and adjust frame timing based on observed results.

### Development scope
- Implement GIF support locally before adding packaging or installation support.
- Keep the existing image mode and working HID behaviour intact.
- Consider video support and additional media readers as later development stages.

### GIF playback timing diagnostics

The `--debug-timing` CLI option reports each frame's target duration, transmission time, remaining wait time, and number of USB chunks. The `--chunk-delay` option controls the optional pause after each chunk.

**Test file:** `~/Pictures/sakuraFlowers.gif`

**Test command:**

```bash
python main.py --mode gif --rotate 90 --debug-timing ~/Pictures/sakuraFlowers.gif
```

**Measured results:**

| Chunk delay | Transmission time | Result |
|---|---:|---|
| 3 ms | Approximately 134–145 ms | Too slow for 100 ms frames |
| 1 ms | Approximately 48–54 ms | Meets 100 ms frame targets |
| 0 ms | Approximately 5.3–5.7 ms | Meets 100 ms and 30 ms targets |

Frames required approximately 43–45 USB chunks each.

**Final behavior:**
- GIF playback defaults to a chunk delay of 0 seconds.
- The optional `--chunk-delay` argument allows a different delay when needed.
- The transmission time is measured using `time.monotonic()`.
- The driver waits only for the remainder of the requested frame duration when transmission finishes early.
- When transmission exceeds the requested duration, no additional wait is added.
- Still-image playback retains its original 3 ms chunk delay.

**Stability test:** The test GIF played without visible flickering, corruption, or stuttering at both 1 ms and 0 ms chunk delays. Playback using the zero-delay default produced consistent transmission measurements.

**Limitations:** These results are from one GIF and one AIO device. They do not establish the physical LCD refresh rate or guarantee identical behavior with every GIF or device.

**Future investigation:** Test additional GIFs with different frame sizes and durations. Investigate video playback separately before implementing the currently unavailable video mode.
