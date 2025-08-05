# Thermalright LCD Control

A Linux application for controlling Thermalright LCD displays with an intuitive graphical interface.

![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)

## Overview

Thermalright LCD Control provides an easy-to-use interface for managing your Thermalright LCD display on Linux systems.
The application features both a desktop GUI and a background service for seamless device control.
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

- 🖥️ **User-friendly GUI** - Modern interface for device configuration
- ⚙️ **Background service** - Automatic device management
- 🎨 **Theme support** - Customizable display themes and backgrounds
- 📋 **System integration** - Native Linux desktop integration

## Supported devices

| VID:PID   | Tested |
|-----------|--------|
| 0416:5302 | Yes    |
| 0416:8001 | No     |
| 0418:5303 | No     |
| 0418:5304 | No     |

## Installation

### Download Packages

Download the appropriate package for your Linux distribution from
the [Releases](https://www.github.com/rejeb/thermalright-lcd-control/releases) page:

- **`.deb`** - For Ubuntu, Debian, and derivatives
- **`.rpm`** - For Fedora, RHEL, CentOS, openSUSE, and derivatives

### Debian/Ubuntu Installation

1. **Download** the `.deb` package:
   ```bash
   wget https://github.com/rejeb/thermalright-lcd-control/blob/master/releases/thermalright-lcd-control_1.0.0_all.deb -P /tmp/
   ```

2. **Install** the package:
   ```bash
   sudo apt install /tmp/thermalright-lcd-control_1.0.0_all.deb
   ```

3. **Fix dependencies** (if needed):
   ```bash
   sudo apt-get install -f
   ```

### Fedora/RHEL/CentOS Installation

1. **Download** the `.rpm` package:
   ```bash
   wget https://github.com/rejeb/thermalright-lcd-control/blob/master/releases/thermalright-lcd-control-1.0.0-1.noarch.rpm -P /tmp/
   ```

2. **Install** the package:
   ```bash
   # Fedora/CentOS 8+
   sudo dnf install /tmp/thermalright-lcd-control-*-1.noarch.rpm
   
   # RHEL/CentOS 7
   sudo yum install /tmp/thermalright-lcd-control-*-1.noarch.rpm
   ```

### openSUSE Installation

1. **Download** the `.rpm` package

2. **Install** the package:
   ```bash
   sudo zypper install /tmp/thermalright-lcd-control-*-1.noarch.rpm
   ```

That's it! The application is now installed and ready to use.

## Usage

### Launch the Application

- **From Applications Menu**: Search for "Thermalright LCD Control" in your application launcher
- **From Terminal**: Run `thermalright-lcd-control`

### System Service

The background service starts automatically after installation. You can manage it using:

# Check service status

sudo systemctl status thermalright-lcd-control.service

# Restart service

sudo systemctl restart thermalright-lcd-control.service

# Stop service

sudo systemctl stop thermalright-lcd-control.service

## System Requirements

- **Operating System**: Ubuntu 20.04+ / Debian 11+ / Other modern Linux distributions
- **Python**: 3.8 or higher (automatically managed)
- **Desktop Environment**: Any modern Linux desktop (GNOME, KDE, XFCE, etc.)
- **Hardware**: Compatible Thermalright LCD device

## Uninstallation

To remove the application:

bash sudo apt-get remove thermalright-lcd-control

To remove configuration files as well:

## Add new device

While this application is made by reverse engineering Thermalrigth application.
This application is compatible with all USB display devices supporting communication through an HID interface.
To add a new device you need to:

- Identify how images are encoded
- Header value or logic used to generate it (for Thermalright devices, each image sent to the device includes a header).
- The size of each paquet sent to the device.
- The display resolution
  And then:
    - Add a new device implementation
      in [display_device.py](src/thermalright_lcd_control/device_controller/display/display_device.py) that extends
      `DisplayDevice`.
    - Override method `_encode_image` to implement the specific device encoding logic and `get_header` for header value.
    - Add device creation in `load_device`.
    - Add device informations in [gui_config.yaml](resources/gui_config.yaml)

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