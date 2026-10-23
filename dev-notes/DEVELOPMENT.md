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


### Image and GIF resizing modes

The `--resize` CLI option controls how still images and animated GIF frames are scaled to the LCD's 480x480 display.

**Available modes:**

| Mode | Behavior |
|---|---|
| `stretch` | Resizes directly to 480x480. May distort the original aspect ratio. This is the default and preserves previous behavior. |
| `fit` | Preserves the aspect ratio, fits the entire image inside 480x480, and centres it on a black background. |
| `crop` | Preserves the aspect ratio, fills the full 480x480 display, and crops excess content from the edges. |

**Usage examples:**

```bash
# Still image, default stretch mode
python main.py --mode image ~/Pictures/example.jpg

# Still image, fit with black background
python main.py --mode image --resize fit ~/Pictures/example.jpg

# Still image, crop with 90-degree clockwise rotation
python main.py --mode image --resize crop --rotate 90 ~/Pictures/example.jpg

# Animated GIF, fit with rotation
python main.py --mode gif --resize fit --rotate 90 ~/Pictures/sakuraFlowers.gif

# Animated GIF, crop
python main.py --mode gif --resize crop ~/Pictures/sakuraFlowers.gif
```

**Implementation:**
- The `--resize` option accepts `stretch`, `fit`, or `crop`; its default is `stretch`.
- Still images and GIF frames share the `encode_image()` function, keeping resizing behavior consistent.
- Rotation is applied before resizing.
- `fit` uses a black RGB background. User-selectable background colours may be added later.
- Existing JPEG compression and frame-size limits remain in place.

**Hardware test results:** Using `~/Pictures/sakuraFlowers.gif` on the ID-Cooling SL360 V2 LCD, the following tests passed:

| Media | Resize mode | Rotation |
|---|---|---|
| Still image | `fit` | None |
| Still image | `fit` | 90 degrees |
| Still image | `crop` | None |
| Still image | `crop` | 90 degrees |
| Still image | `stretch` (default) | 90 degrees |
| Animated GIF | `fit` | 90 degrees |
| Animated GIF | `crop` | None |
| Animated GIF | `crop` | 90 degrees |
| Animated GIF | `stretch` (default) | 90 degrees |

These tests confirmed that the selected modes work on the physical display, including rotation. Testing is not exhaustive across all image formats, aspect ratios, or GIFs.

### Video playback dependency

FFmpeg is a required system dependency for the planned video playback functionality. It will decode video files into frames for processing by the existing Pillow-based image pipeline and transmission to the LCD.

The installation method has not yet been decided. Fedora compatibility is the initial target; document and implement dependency installation checks once the setup method is chosen.

## Video Ctrl+C and delayed LCD shutdown

**Status:** Under investigation

### Observed behaviour

When playing `~/Videos/RainyForest.mp4` in video mode with `--resize crop`:

1. Pressing Ctrl+C stops video playback immediately.
2. After a brief pause, the terminal prints:
   - `Closing LCD USB device...`
   - `LCD USB device closed in 0.01 seconds.`
   - `Video playback stopped.`
3. The program returns to the shell prompt.
4. The LCD remains on for a longer pause, then shuts off.

The process is no longer stuck after the interrupt handler was added. The remaining delay is between the program exiting and the LCD shutting off.

### Changes and checks completed

- Added a `KeyboardInterrupt` handler to the video branch in `main.py`.
- Added a `finally` block to close the FFmpeg frame generator.
- Temporarily measured dev.close() at approximately 0.01 seconds; the diagnostic prints have since been removed.
- `python -m py_compile main.py core.py image.py` passes.
- The HID device close was measured at approximately 0.01 seconds.
- The current `send_video()` cleanup closes the HID device in a `finally` block.
- `send_commands()` sends the `LIG` brightness command and deliberately skips `DIS`.

### Current assessment

The measured USB close time does not explain the longer delay before the LCD shuts off. The delay appears to occur after the application has returned to the shell.

The LCD may retain its last frame after the USB connection closes and shut down later due to device or firmware behaviour. This explanation has not yet been confirmed.

### Protocol caution

The original project's protocol notes describe `DIS` as a disconnect/clear command. However, testing on this SL360 V2 showed that skipping `DIS` prevents the built-in default text screen from reappearing.

Do not reintroduce `DIS` as part of the interrupt fix without a separate, controlled test.

### Follow-up investigation

- [x] Compare still-image and video exit behaviour; the delayed shutdown occurs after both.
- [x] Confirm that the measured USB close time does not explain the observed delay.
- [ ] Investigate the LCD's behaviour after the HID device closes.
- [ ] Keep the current no-`DIS` behaviour unless a controlled test demonstrates a better result.

### Follow-up: still-image shutdown delay

**Result:** The delayed LCD shutdown also occurs after still-image playback. The behaviour is therefore not limited to video mode.

The application can return to the shell while the LCD remains lit for a while before shutting off. During video interruption testing, `dev.close()` completed in approximately 0.01 seconds, so the observed delay occurs after the HID close call returns.

**Conclusion:** The delay is reproducible in both still-image and video modes. Its exact cause remains unconfirmed; do not attribute it definitively to the device firmware without further evidence.

The issue is documented and is not being investigated further for this change set.
