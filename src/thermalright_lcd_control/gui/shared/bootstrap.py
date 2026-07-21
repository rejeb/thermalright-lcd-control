# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Bootstrap du point d'entrée GUI.

Construit tout ce qui précède la fenêtre : QApplication, détection des devices,
EventBus et DeviceController. ``main()`` n'a plus qu'à instancier la fenêtre.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.common.logging_config import get_gui_logger, get_log_file_path
from thermalright_lcd_control.gui.utils.config_loader import load_config
from thermalright_lcd_control.gui.utils.usb_detector import USBDeviceDetector


def append_led_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return ``devices`` plus any LED controllers currently plugged in.

    LED devices are auto-detected over USB (presence + HID handshake); nothing
    is appended when no LED hardware is connected. Existing entries preserved.
    """
    from thermalright_lcd_control.device_controller.led.detect import (
        detect_led_devices,
    )
    result = list(devices)
    try:
        result.extend(detect_led_devices())
    except Exception as e:   # detection must never block GUI startup
        get_gui_logger().error(f"LED auto-detection failed: {e}", exc_info=True)
    return result


@dataclass
class GuiRuntime:
    app: QApplication
    config_file: str
    config: dict[str, Any]
    devices: list[dict[str, Any]]
    bus: Any
    controller: Any
    logger: Any


def create_runtime(config_file: str | None) -> GuiRuntime:
    """QApplication + devices + EventBus + DeviceController, prêts pour la fenêtre."""
    logger = get_gui_logger()
    logger.info(f"Starting Thermalright LCD Control GUI (logs: {get_log_file_path()})")

    # Before any worker thread spawns: without the cap, glibc grows one malloc
    # arena per concurrently-allocating thread (render loops + metrics + Qt)
    # and each arena retains its own free pages.
    from thermalright_lcd_control.device_controller.display.utils import cap_malloc_arenas
    cap_malloc_arenas(2)

    # Facteur d'échelle appliqué tel quel (150 % → ×1,5) : sans cette politique,
    # l'arrondi des facteurs fractionnaires varie selon la distro (UI ×1 ou ×2).
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    # Lancée via `python -m …`, Qt dériverait le WM_CLASS de argv[0] (« python3 »),
    # que GNOME ne peut pas rapprocher du .desktop → icône engrenage générique
    # dans le dock. On force argv[0] (WM_CLASS sous X11) et le desktopFileName
    # (app_id sous Wayland) au nom du fichier .desktop installé.
    argv = ["thermalright-lcd-control"] + sys.argv[1:]
    app = QApplication(argv)
    app.setApplicationName("thermalright-lcd-control")
    app.setDesktopFileName("thermalright-lcd-control")
    app.setApplicationDisplayName("Thermalright LCD Control")
    app.setQuitOnLastWindowClosed(False)  # closing the window hides to tray

    if config_file is None:
        config_file = "gui_config.yaml"
    logger.info(f"Using configuration file: {config_file}")

    cfg = load_config(config_file)
    config_dir = cfg.get("paths", {}).get("service_config", "./resources/config")

    # trcc-style zero-touch: probe-register connected known devices BEFORE the
    # configured list is read, so a first launch opens with the device combobox
    # filled instead of the add-device form. When nothing is detected and
    # nothing is configured, the window still opens the add form (its existing
    # empty-list behavior). Best-effort: a probe failure must not block the GUI.
    from thermalright_lcd_control.device_controller.display.device_registry import (
        register_detected_devices,
    )
    try:
        added = register_detected_devices(config_dir)
        if added:
            logger.info("Auto-registered detected device(s): "
                        + ", ".join(e["id"] for e in added))
    except Exception as e:
        logger.error(f"Device auto-detection failed: {e}", exc_info=True)

    detector = USBDeviceDetector(config_file)
    devices = append_led_devices(detector.get_devices())
    logger.info(f"Detected {len(devices)} supported device(s)")

    from thermalright_lcd_control.device_controller.controller import DeviceController
    from thermalright_lcd_control.device_controller.display.event_bus import EventBus

    # Icône applicative (fenêtre + repli si l'association au .desktop échoue).
    icon_path = cfg.get("paths", {}).get("icon_path")
    if icon_path and Path(icon_path).exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    bus = EventBus()
    active_id = devices[0].get("id") if devices else None
    logger.info(f"Active device id: {active_id}")
    media_endpoint = cfg.get("media_endpoint")
    controller = DeviceController(config_dir, event_bus=bus, active_device_id=active_id,
                                  media_endpoint=media_endpoint)

    return GuiRuntime(app=app, config_file=config_file, config=cfg,
                      devices=devices, bus=bus, controller=controller,
                      logger=logger)


def run_window(runtime: GuiRuntime, window, minimized: bool) -> None:
    """Affiche la fenêtre, démarre le controller et entre dans la boucle Qt."""
    if minimized:
        # Autostart at login: stay silently in the system tray.
        runtime.logger.info("Starting minimized to the system tray")
        window.hide()
    else:
        window.showMaximized()
    runtime.controller.start_async()      # device threads start in the background
    runtime.logger.info("GUI started; entering Qt event loop")
    exit_code = runtime.app.exec()
    runtime.logger.info(f"GUI event loop exited with code {exit_code}")
    sys.exit(exit_code)
