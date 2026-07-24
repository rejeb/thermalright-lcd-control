# Thermalright LCD Control

A Linux application for controlling Thermalright LCD displays with an intuitive graphical interface.

![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)
![version](https://img.shields.io/badge/version-2.0.0-green.svg)

## Overview

Thermalright LCD Control provides an easy-to-use interface for managing your Thermalright LCD display on Linux systems.

Since version 2.0, the application is a single desktop app: the GUI embeds the device controller, so there is no
separate root service anymore. Device access is granted through udev rules, and the app can start automatically with
your session (minimized to the system tray).

I performed reverse engineering on the Thermalright Windows application to understand its internal mechanisms.

During my analysis, I identified four different USB VID:PID combinations handled by the Windows application, all sharing
the same interaction logic.

Since I have access only to the Frozen Warframe 420 BLACK ARGB, my testing was limited exclusively to this specific
device.

Also, this application implements reading metrics from Amd, Nvidia, and Intel GPU. My testing was limited to Nvidia GPU.

Feel free to contribute to this project and let me know if the application is working with other devices.

For backgrounds, i have included all media formats supported by the Windows application
and added the option to select a collection of images to cycle through on the display.

## Features

- 🖥️ **User-friendly GUI** - Modern native Qt interface with light/dark theme
- ⚙️ **Single-app architecture** - The device controller runs inside the app; no root service needed (udev rules grant
  device access)
- 🔌 **Multi-device support** - Several displays can be connected and driven at the same time, each with its own
  configuration; a per-device tab bar lets you switch between them, and edits are saved automatically before switching
- 🔎 **Automatic device detection** - Connected devices are detected on the fly: plug or unplug a display and it appears
  or disappears in the GUI without restarting the app (its configuration is kept for when it comes back)
- ➕ **Add devices without code** - Register a new device from the GUI (or a small YAML file) using the generic,
  data-driven driver: pick transport, encoding and header format — no Python required. Known devices pre-fill the form
  automatically
- ⚡ **Fast device switching** - Cached thumbnails and per-device render engines make switching between devices and
  themes near-instant
- 🎨 **Theme support** - Customizable display themes with bundled presets, per-resolution backgrounds and foregrounds
  (the matching foreground is auto-selected for your resolution)
- 🖼️ **Rich media backgrounds** - Images, animated GIFs and videos; imported media is automatically resized to your
  screen resolution, and bundled video backgrounds are downloaded on demand
- 🧩 **Widget editor** - Drag-and-drop metric, clock, date and text widgets with per-widget font, size, bold/italic,
  color and precision (multi-selection supported)
- 🔄 **Display rotation** - 0°/90°/180°/270° orientation with rotation-aware backgrounds and foregrounds
- 📊 **Hardware & OS metrics** - all displayable as widgets, grouped by device:
    - **CPU**: temperature, usage, frequency
    - **GPU**: temperature, usage, frequency (AMD, Nvidia and Intel)
    - **Memory**: RAM usage, RAM used/available (GB), swap usage
    - **Disk**: filesystem usage, read/write throughput (MB/s)
    - **Network**: download/upload throughput (MB/s)
    - **System**: uptime, load average, process count
- 🔤 **Font management** - Use any installed system font (plus bundled fallbacks) in your themes
- 💡 **RGB LED controller support** - Drives Thermalright digital LED coolers (the `0416:8001` controller),
  auto-detected over USB with the hardware layout identified via the device handshake. A dedicated, kind-aware control
  panel provides:
    - global colour (colour picker, RGB, brightness, presets) and On/Off
    - six animation modes: static, breathing, colourful, rainbow, temperature-linked, load-linked
    - per-zone colour/brightness/on-off for multi-zone models (PA120, LF10), with an optional zone-sync carousel
    - CPU/GPU sensor linkage and a diagnostic test mode
    - a **live preview that renders the real per-model layout** — including the actual digit/clock readout for the
      digital segment displays (temperature, load, memory/disk stats, clock)
  - 12 cooler layouts supported: AX120, PA120, AK120, LC1, LF8, LF10, LF11, LF12, LF13, LF15, CZ1, LC2
- 📋 **System integration** - Tray icon, session autostart (starts minimized), desktop notifications; rendering pauses
  while the window is hidden to save CPU

## Supported devices

### LCD displays

| VID:PID   | Chip / Family                    | Thermalright product(s)                                    | Protocol      |
|-----------|----------------------------------|------------------------------------------------------------|---------------|
| 0402:3922 | —                                | Frozen Warframe 420 BLACK ARGB *(tested)*                  | SCSI BOT      |
| 0416:5302 | Winbond USBDISPLAY               | Frozen Magic 240 / 360 (HID variants)                      | HID type 2    |
| 0416:5406 | Winbond LCD (SCSI)               | Frozen Warframe / Magic (SCSI variant)                     | SCSI          |
| 0416:5408 | Trofeo Vision (LY)                | **Trofeo Vision                                           | LY bulk       |
| 0416:5409 | Trofeo Vision (LY1)              | **Trofeo Vision (LY1 firmware)                             | LY bulk       |
| 0418:5303 | ALi Corp LCD (HID type 3)        | Frozen Magic 360 SCENIC / AIO 480 variants                 | HID type 3    |
| 0418:5304 | ALi Corp LCD (HID type 3)        | Frozen Magic 360 SCENIC / AIO 480 variants                 | HID type 3    |
| 87AD:70DB | ChiZhu Tech GrandVision family   | AIO variants with 320x320 or 480x480 screen                | | USB Bulk    |
| 87CD:70DB | ChiZhu Tech (variant)            | AIO variants (alternate firmware)                          | USB Bulk      |

> If you own one of the other devices, please test and report — see [Contributing](#-contributing).
>
> If your device is not in the list, you can most likely add it yourself without writing any code, thanks to the
> generic device support: see the [Add new device](#add-new-device) section.

### RGB LED controllers

| VID:PID   | Device                              | Supported cooler layouts                                              |
|-----------|-------------------------------------|-----------------------------------------------------------------------|
| 0416:8001 | Thermalright digital LED controller | AX120, PA120, AK120, LC1, LF8, LF10, LF11, LF12, LF13, LF15, CZ1, LC2 |

The LED controller is auto-detected over USB; the specific cooler layout is resolved at connection time from the
device handshake. A plugged-in LED controller appears as its own device tab with the dedicated LED control panel.

> **Note:** LED support was developed against the reference protocol and firmware layouts. If you own one of these
> coolers, testing and feedback are very welcome — see [Contributing](#-contributing).

## Installation

### Download Packages

Download the appropriate package for your Linux distribution from
the [Releases](https://www.github.com/rejeb/thermalright-lcd-control/releases) page:

- **`.targ.gz`** - For any distribution

### Installation

1. **Check** for required dependencies:
   /!\ Make sure you have these required dependencies installed:
    - python3
    - python3-pip
    - python3-venv
    - libhidapi-* or hidapi depending on your distribution

2. **Download** the `.tar.gz` package:
   ```bash
   wget https://github.com/rejeb/thermalright-lcd-control/releases/download/2.0.0/thermalright-lcd-control-2.0.0.tar.gz -P /tmp/
   ```

3. **Untar** the archive file:
   ```bash
   cd /tmp
   
   tar -xvf thermalright-lcd-control-2.0.0.tar.gz
   ```

4. **Install** application:
   ```bash
   cd /thermalright-lcd-control
   
   sudo bash install.sh
   ```

That's it! The application is now installed. You can see the default theme displayed on your Thermalright LCD device.

## Troubleshooting

If nothing is displayed on your device:

- Make sure the application is running (check the system tray)
- Check the application logs located in `~/.local/state/thermalright-lcd-control/` (also reachable from the tray menu
  via "Open Logs")
- Make sure the udev rules were installed (`/etc/udev/rules.d/99-thermalright.rules`) and re-plug the device

If the device is detected but the display stays black, the frame header is probably not correct for your device.
If an image is displayed but looks blurry or scrambled, the image encoding does not match your device.
In both cases, see the [Add new device](#add-new-device) section: with the generic device support you can adjust the
header and encoding from the GUI without touching any code.

## Usage

### Launch the Application

- **From Applications Menu**: Search for "Thermalright LCD Control" in your application launcher
- **From Terminal**: Run `thermalright-lcd-control`

### Autostart and system tray

The application starts automatically with your session (minimized to the system tray) and keeps driving the display in
the background. Closing the window minimizes to the tray instead of quitting; use the tray menu to reopen the window,
open the logs or quit the application.

While the window is hidden, the on-screen preview is paused to keep CPU usage minimal — the device itself keeps
updating.

## System Requirements

- **Operating System**: Ubuntu 20.04+ / Debian 11+ / Other modern Linux distributions
- **Python**: 3.8 or higher (automatically managed)
- **Desktop Environment**: Any modern Linux desktop (GNOME, KDE, XFCE, etc.)
- **Hardware**: Compatible Thermalright LCD device

## Add new device

There are two ways to add support for a new device:

- **Generic device (recommended, no code)**: describe the device (transport, image encoding, frame header) either
  directly from the GUI with the "+" button in the header, or in a small `device_<id>.yaml` file. The data-driven
  generic driver does the rest.
- **Native device (Python code)**: implement a dedicated device class, for protocols the generic driver cannot
  express.

In [HOWTO.md](doc/HOWTO.md) I detail all the steps I went through to find out how my device works (USB capture and
protocol reverse engineering), and how to add a new device using either approach.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author

**REJEB BEN REJEB** - [benrejebrejeb@gmail.com](mailto:benrejebrejeb@gmail.com)

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the project
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -am 'Add my feature'`)
4. Push to your branch (`git push origin feature/my-feature`)
5. Create a Pull Request
