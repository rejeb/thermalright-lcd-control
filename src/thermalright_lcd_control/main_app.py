# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Entry point for Thermalright LCD Control GUI (native Qt Widgets UI).

The whole pre-window construction (QApplication, device detection, EventBus,
DeviceController) lives in ``gui.shared.bootstrap``.
"""

import argparse

from thermalright_lcd_control.gui.shared.bootstrap import create_runtime, run_window


def main(config_file=None, minimized=False):
    rt = create_runtime(config_file)

    from thermalright_lcd_control.gui.native.main_window import NativeMainWindow
    window = NativeMainWindow(rt.config_file, rt.devices, event_bus=rt.bus,
                              controller=rt.controller)
    run_window(rt, window, minimized)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thermalright LCD Control GUI")
    parser.add_argument('--config', required=True,
                        help="Path to GUI configuration file (gui_config.yaml)")
    parser.add_argument('--minimized', action='store_true',
                        help="Start hidden in the system tray (used at login autostart)")
    args = parser.parse_args()
    main(args.config, minimized=args.minimized)
