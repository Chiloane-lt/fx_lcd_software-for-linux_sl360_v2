# FX LCD Linux Driver — SL360 V2 Personal Version

An unofficial Linux driver adaptation for the **ID-COOLING SL360 V2 AIO liquid cooler with LCD**, based on the original [fx_lcd_software-for-linux](https://github.com/w1n-ror/fx_lcd_software-for-linux) project.

The original project targets ID-COOLING FX-series LCD coolers. This personal version adapts the HID communication and image handling for the SL360 V2, tested on Fedora Linux. It sends images directly to the cooler over USB HID without requiring the Windows vendor application, Wine, or a virtual machine.

**This is a hardware-specific adaptation under development.** Compatibility with other coolers has not been established.

## Differences from the original project

| Area | Original project | This SL360 V2 version |
| --- | --- | --- |
| Target hardware | ID-COOLING FX LCD series | ID-COOLING SL360 V2 |
| USB VID:PID | `2000:3000` | `2000:3002` |
| Image resolution | 240 × 240 | 480 × 480 |
| Startup commands | Sends `DIS` and `LIG` | Sends `LIG`; skips `DIS` |
| Image transfer | HID image chunks | Retains chunk streaming with a 3 ms delay |
| Command-line interface | `--mode`, `--rotate` | Retains the original interface |

The changes above reflect the current implementation and tests on the SL360 V2. They should not be assumed to work identically on other devices.

## Current status

### Working and tested
- Detects the cooler using USB vendor ID `0x2000` and product ID `0x3002`.
- Displays images at 480 × 480.
- Supports the original image-mode command-line interface and rotation options.
- Streams image data in 1024-byte chunks, prefixed with HID report ID `0x00`.
- Uses the `LIG` brightness command with brightness value `0x64` (100%).
- Skipping `DIS` prevents the built-in default text screen from reappearing in the observed tests.

### Known limitations
- The image remains visible while the streaming program runs.
- When the HID connection closes, the display shuts down after approximately 2–3 seconds in observed tests.
- The exact reason for this shutdown behaviour has not been confirmed.
- Video mode, temperature overlays, and a graphical interface are not implemented.
- Only the ID-COOLING SL360 V2 described here has been tested with this adaptation.

## Hardware and environment

- Cooler: ID-COOLING SL360 V2
- USB vendor ID: `0x2000`
- USB product ID: `0x3002`
- USB product string observed: `HOTSPOTEKUSB HID DEMO`
- Display resolution observed: 480 × 480
- Tested operating system: Fedora 44
- Python dependencies: `hidapi`, `Pillow`

Find your USB device ID with:

```bash
lsusb
```

If your device does not appear as `2000:3002`, do not assume these settings are suitable for it.

## Requirements

Python 3.10 or later, `hidapi`, and Pillow.

On Fedora, install the system packages:

```bash
sudo dnf install python3 python3-pip python3-pillow
```

Create and activate a project-local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python dependencies:

```bash
python -m pip install hidapi Pillow
```

## Local development setup

Clone this personal repository:

```bash
git clone https://github.com/Chiloane-lt/fx_lcd_software-for-linux_sl360_v2.git
cd fx_lcd_software-for-linux_sl360_v2
```

If you are already working in the project directory, you do not need to clone it again.

### USB permissions

The program needs permission to access the cooler's HID device. On Fedora, a udev rule can grant access to the logged-in desktop user.

Create the rule:

```bash
sudo nano /etc/udev/rules.d/99-fx-lcd.rules
```

Add:

```udev
SUBSYSTEM=="hidraw", KERNEL=="hidraw*", ATTRS{idVendor}=="2000", ATTRS{idProduct}=="3002", TAG+="uaccess"
```

Save the file, then reload the rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and reconnect the cooler if necessary. If access still fails, check the device permissions and the system's udev logs before changing permissions more broadly.

## Usage

Run the driver directly from the project directory:

```bash
python main.py --mode image /path/to/image.png
```

Rotate the image clockwise by 90 degrees:

```bash
python main.py --mode image --rotate 90 /path/to/image.png
```

Supported rotation values are `0`, `90`, `180`, and `270`.

| Argument | Description |
| --- | --- |
| `--mode {image,video}` | Required mode argument; image mode is implemented |
| `path` | Required path to the source image |
| `--rotate {0,90,180,270}` | Clockwise rotation; defaults to `0` |
| `-h, --help` | Display command-line help |

The program resizes the image to 480 × 480, converts it to RGB, encodes a baseline JPEG, and streams the frame to the LCD.

**The image stream runs continuously.** Press `Ctrl+C` to stop the program. Based on current tests, the LCD shuts down shortly after the HID connection closes.

Video mode is not implemented. Do not use it expecting video playback to work.

## Troubleshooting

- **Permission denied:** Check the udev rule, reconnect the cooler, and confirm that your user can access its HID device.
- **Device not found:** Run `lsusb` and confirm the device's VID:PID is `2000:3002`.
- **Image is sideways or upside down:** Try `--rotate 90`, `--rotate 180`, or `--rotate 270`.
- **The image disappears after the program exits:** This matches the behaviour observed so far when the HID connection closes.
- **The built-in text screen reappears:** Confirm that the `DIS` command has not been reintroduced into `send_commands()`.

## Protocol notes

The implementation uses USB HID writes with report ID `0x00`.

The image frame contains a 32-byte header followed by JPEG data:

```text
43 52 54 00 00   "CRT"
44 52 41 00 00   "DRA"
LL LL            Payload length: 32 + JPEG size, big-endian
B1               Magic byte
00 * 19          Padding
FF D8 ... FF D9  Baseline JPEG
```

The frame is sent in 1024-byte chunks, each prefixed with report ID `0x00`. The delay between chunks is approximately 3 ms; faster writes may overflow the device.

Commands used by this version:

- `LIG` (`4C 49 47 00 00` followed by a brightness byte): brightness control. This implementation uses `0x64` (100%).
- `DIS` (`44 49 53 00 00` followed by zero padding): the original project uses this as a disconnect/clear command. This version deliberately skips it because testing showed that doing so prevented the built-in default text screen from reappearing.

The precise firmware behaviour when the HID connection closes remains unconfirmed.

## Development notes

Additional hardware observations, test results, and local backups are kept in the `dev-notes/` directory during development. Local backups and test artifacts are excluded from Git; `dev-notes/DEVELOPMENT.md` records the current findings.

This project is still being tested locally. It has not been packaged for installation.

## Roadmap

- [ ] Investigate display behaviour after the HID connection closes
- [ ] Implement video mode
- [ ] Add temperature overlay
- [ ] Handle EXIF orientation automatically
- [ ] Develop a graphical interface
- [ ] Prepare packaging only after local testing is complete

## Disclaimer and attribution

This is an unofficial community adaptation and is not affiliated with or endorsed by ID-COOLING.

The work builds on the original [fx_lcd_software-for-linux](https://github.com/w1n-ror/fx_lcd_software-for-linux) project. Please consult the original repository for its licensing terms.

This software communicates with the LCD display; it does not control the cooler's fans or pump. Use it at your own risk.

## Contributing and compatibility reports

Reports about other devices are welcome. Include the USB VID:PID from `lsusb`, your operating system, and relevant logs where possible. Compatibility with other hardware should be tested rather than assumed.
