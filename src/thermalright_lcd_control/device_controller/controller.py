# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""In-process device controller.

Wraps :class:`DeviceLoader` so the device threads run inside the GUI process
instead of a separate root service. It never calls ``sys.exit``: a missing
device is logged and the app keeps running (the GUI stays usable).
"""
from __future__ import annotations

import threading

from thermalright_lcd_control.common.logging_config import get_service_logger
from thermalright_lcd_control.device_controller.display.device_loader import DeviceLoader
from thermalright_lcd_control.device_controller.display.device_presence_monitor import (
    DevicePresenceMonitor,
)


class DeviceController:
    def __init__(self, config_dir: str, event_bus=None, active_device_id=None,
                 media_endpoint: str | None = None):
        self.config_dir = config_dir
        self.event_bus = event_bus
        self.active_device_id = active_device_id
        # Configured bundled-video download host (gui_config.yaml), forwarded to
        # DeviceLoader → each engine's FrameManager.
        self.media_endpoint = media_endpoint
        self.logger = get_service_logger()
        self._loader: DeviceLoader | None = None
        self._presence_monitor: DevicePresenceMonitor | None = None
        self._started = False
        self._media_active = True
        self._lock = threading.Lock()

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def _engines(self) -> list:
        return self._loader.active_engines() if self._loader is not None else []

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self.logger.info(
                f"Starting device controller (active device id: {self.active_device_id})")
            loader = DeviceLoader(self.config_dir, event_bus=self.event_bus,
                                  active_device_id=self.active_device_id,
                                  media_active=self._media_active,
                                  media_endpoint=self.media_endpoint)
            loader.migrate_device_info()
            loader.autodetect_devices()
            devices = loader.start_all()
            if not devices:
                self.logger.warning(
                    "No device present; controller idle (GUI still usable)")
            else:
                self.logger.info(f"Device controller started with {len(devices)} engine(s)")
            self._loader = loader
            self._started = True
            # Engines built while the window is hidden must start in low-memory
            # mode too (e.g. autostart to tray, or a restart while minimized).
            self._apply_media_active()
            self._presence_monitor = DevicePresenceMonitor(
                self.config_dir, self, event_bus=self.event_bus)
            self._presence_monitor.start()

    def set_media_active(self, active: bool) -> None:
        """Window shown/hidden: toggle the engines' low-memory mode. When
        inactive, each engine drops its decoded media and keeps only the
        ready-to-send encoded cache."""
        self._media_active = bool(active)
        self._apply_media_active()

    def _apply_media_active(self) -> None:
        """Per-engine media retention: an engine keeps its decoded media only
        when the window is visible AND it drives the previewed device (all
        engines when no active device id is known)."""
        for engine in self._engines:
            setter = getattr(engine, "set_media_active", None)
            if callable(setter):
                setter(self._media_active and (
                    self.active_device_id is None
                    or str(getattr(engine, "_reload_id", "")) == str(self.active_device_id)))

    def start_async(self) -> None:
        """Start on a background thread so device-open I/O never blocks the GUI."""
        threading.Thread(
            target=self.start, name="device-controller-start", daemon=True).start()

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self.logger.info("Stopping device controller")
            if self._presence_monitor is not None:
                self._presence_monitor.stop()
                self._presence_monitor = None
            if self._loader is not None:
                self._loader.stop_all()
            self._loader = None
            self._started = False
            self.logger.info("Device controller stopped")

    def restart(self) -> None:
        """Stop and start again so a changed ``devices.yaml`` takes effect.

        Needed when a device's registry entry changes (driver mode, transport,
        encoding…): the running engine/sink was built from the old entry and must
        be rebuilt. Cheap to call when not started (just starts)."""
        self.stop()
        self.start()

    def restart_async(self) -> None:
        """Restart on a background thread so the join/USB I/O never blocks the GUI."""
        threading.Thread(
            target=self.restart, name="device-controller-restart",
            daemon=True).start()

    def add_device_engine(self, device_id: str) -> None:
        """Build+start a single device's engine (new entry, or one that just
        became present), without touching any other running engine."""
        with self._lock:
            if self._loader is None:
                return
            self._loader.start_one(device_id)
        self._apply_media_active()

    def remove_device_engine(self, device_id: str) -> None:
        """Stop+close a single device's engine (releasing its
        DisplayGenerator), without touching any other running engine."""
        with self._lock:
            if self._loader is None:
                return
            self._loader.stop_one(device_id)
        self._apply_media_active()

    def update_device_engine(self, old_id: str, new_id: str) -> None:
        """Rebuild only the edited device's engine (its entry data changed:
        transport, encoding, resolution, id...). Other engines are untouched."""
        with self._lock:
            if self._loader is None:
                return
            self._loader.stop_one(old_id)
            self._loader.start_one(new_id)
        self._apply_media_active()

    def set_active_device(self, device_id) -> None:
        """Set which device the GUI is previewing. Absent devices never have
        an engine (see DeviceLoader.start_one), so this only needs to update
        each running engine's media-retention flag — no rebuild."""
        if str(device_id) == str(self.active_device_id):
            return
        self.logger.info(
            f"Active device changed: {self.active_device_id} -> {device_id}")
        self.active_device_id = device_id
        self._apply_media_active()

    def last_base_frame(self, device_id):
        """Return the current base (bg+fg, rotated) frame for ``device_id``.

        Read by the GUI preview each tick, via the per-device DisplayGenerator
        singleton shared with the render loop. Non-advancing: the render loop
        owns frame timing. None when the device has no generator or its media
        is dropped."""
        from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator
        gen = DisplayGenerator.get(str(device_id))
        if gen is None:
            return None
        return gen.current_base_frame()
