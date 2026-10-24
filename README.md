# FX LCD Linux Driver — SL360 V2 Personal Version

An unofficial Linux driver adaptation for the **ID-COOLING SL360 V2 AIO liquid cooler with LCD**, based on the original [fx_lcd_software-for-linux](https://github.com/w1n-ror/fx_lcd_software-for-linux) project.

The original project targets ID-COOLING FX-series LCD coolers. This personal version adapts the HID communication and image handling for the SL360 V2, tested on Fedora Linux. It sends images directly to the cooler over USB HID without requiring the Windows vendor application, Wine, or a virtual machine.

**This is a hardware-specific adaptation under development.** Compatibility with other coolers has not been established.

## Differences from the original project

| Area | Original project | This SL360 V2 version |
| --- | --- | --- |
| Target hardware | ID-COOLING FX LCD series | ID-COOLING SL360 V2 |
| USB VID:PID | `2000:3000` | Configurable; defaults to `2000:3002` |
| Image resolution | 240 × 240 | 480 × 480 |
| Startup commands | Sends `DIS` and `LIG` | Sends `LIG`; skips `DIS` |
| Image transfer | HID image chunks | Retains chunk streaming with a 3 ms delay |
| Command-line interface | `--mode`, `--rotate` | Retains the original interface |

The changes above reflect the current implementation and tests on the SL360 V2. They should not be assumed to work identically on other devices.

## Current status

### Implemented and covered by automated tests

- Uses configurable USB vendor and product IDs, defaulting to `0x2000:0x3002` for the tested SL360 V2.
- Displays images at 480 × 480.
- Supports image, animated GIF, and video playback paths.
- Streams image data in 1024-byte chunks, prefixed with HID report ID `0x00`.
- Uses the `LIG` brightness command with brightness value `0x64` (100%).
- Skips `DIS` because observed tests showed that doing so prevented the built-in default text screen from reappearing.
- Reopens the video frame generator for each playback pass so video playback can loop.
- Includes a foreground `service` command intended for systemd-managed playback.
- Includes process detection and stop handling that distinguishes service playback from manually started playback.
- Includes automated tests for configuration, media validation, runtime helpers, process detection, and video looping. Tests use mocked USB hardware.

### Known limitations and validation status

- Automated tests do not establish that the service works correctly on every Fedora installation or with every compatible device.
- The systemd service setup on the development machine previously failed because SELinux denied execution of Python from the project virtual environment under the user's home directory. SELinux has not been disabled to work around this.
- A supported installer and uninstaller have not yet been implemented.
- The display's behavior after the HID connection closes remains incompletely understood.
- Temperature overlays and a graphical interface are not implemented.
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

Python 3.10 or later, `hidapi`, Pillow, and FFmpeg (required for video decoding and playback).

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

### USB device configuration

The USB vendor ID (VID) and product ID (PID) are saved in:

`~/.config/fx-lcd/config.json`

The default IDs for the tested SL360 V2 are VID `0x2000` and PID `0x3002`.

Set the IDs with:

```bash
python main.py set-device 0x2000 0x3002
```

Replace these values with the VID and PID reported by `lsusb` if using a different compatible device. The command accepts hexadecimal values (with the `0x` prefix) and saves them as integers in the JSON configuration. All USB communication functions use these saved IDs.

Changing the IDs does not change the LCD communication protocol or guarantee compatibility with another device. If the IDs change, review `/etc/udev/rules.d/99-fx-lcd.rules` and update its matching IDs as needed. The command only saves configuration; it does not connect to the LCD.

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
| `--mode {image,gif,video}` | Select image, animated GIF, or video playback |
| `path` | Path to the source media file |
| `--rotate {0,90,180,270}` | Clockwise rotation; defaults to `0` |
| `--resize {stretch,fit,crop}` | Select how media is resized to the display |
| `-h, --help` | Display command-line help |

The program resizes the image to 480 × 480, converts it to RGB, encodes a baseline JPEG, and streams the frame to the LCD.

**The image stream runs continuously.** Press `Ctrl+C` to stop the program. Based on current tests, the LCD shuts down shortly after the HID connection closes.

Video playback loops continuously. Each pass obtains a fresh frame generator so the video can restart after reaching its end. Press `Ctrl+C` to stop manually started playback.

### Managed playback

The project includes a foreground service command that loads the saved media and playback settings. It is intended to be run by systemd:

```bash
python main.py service
```

For a manually managed playback process, use:

```bash
python main.py start
python main.py stop
```

When playback is managed by the systemd service, stop it through systemd instead

```bash
sudo systemctl stop fx-lcd.service
```

The service command and process-handling code have automated test coverage. A complete, SELinux-compatible installation workflow has not yet been established, so these commands should not be taken as proof that systemd startup is ready on every system.

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

This project is under active development. Playback and runtime-helper changes have automated test coverage, but installation, removal, and systemd startup still require further validation. The installer and uninstaller are planned next.

## Roadmap

- [ ] Investigate display behaviour after the HID connection closes
- [x] Implement looping video playback
- [x] Add a foreground service command and managed-process detection
- [ ] Complete and validate systemd startup with SELinux enforcing
- [ ] Implement an installer and uninstaller
- [ ] Test installation and removal in a clean Fedora environment
- [ ] Add temperature overlay
- [ ] Handle EXIF orientation automatically
- [ ] Develop a graphical interface
- [ ] Consider RPM packaging after the installation workflow is validated

## Disclaimer and attribution

This is an unofficial community adaptation and is not affiliated with or endorsed by ID-COOLING.

This project builds on the original [fx_lcd_software-for-linux](https://github.com/w1n-ror/fx_lcd_software-for-linux) project. Please consult the original repository for its licensing terms.

**AI assistance disclaimer:** AI tools were used to assist with software development, debugging, test development, and documentation. The project is still being tested, and AI assistance does not guarantee correctness, hardware compatibility, or safety. Changes should be reviewed and validated on the intended hardware before relying on them.

This software communicates with the LCD display; it does not control the cooler's fans or pump. Use it at your own risk.

## Contributing and compatibility reports

Reports about other devices are welcome. Include the USB VID:PID from `lsusb`, your operating system, and relevant logs where possible. Compatibility with other hardware should be tested rather than assumed.
