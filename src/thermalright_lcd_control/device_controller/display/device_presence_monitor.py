# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Background USB presence poller.

Every ``interval`` seconds, diffs the set of currently-detected configured
devices against the previous poll. Newly-absent devices are torn down
(engine + DisplayGenerator released); newly-present ones get a fresh engine.
Config files are never touched — only in-memory engine instances and the
published device list."""
from __future__ import annotations

import threading

from thermalright_lcd_control.common.logging_config import get_service_logger
from thermalright_lcd_control.device_controller.display import device_registry
from thermalright_lcd_control.device_controller.display.event_bus import Topic


class DevicePresenceMonitor:
    def __init__(self, config_dir: str, controller, event_bus=None,
                 interval: float = 5.0):
        self.config_dir = config_dir
        self.controller = controller
        self.event_bus = event_bus
        self.interval = interval
        self.logger = get_service_logger()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._present: set[str] = set()

    def start(self) -> None:
        self._present = device_registry.present_device_ids(self.config_dir)
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="device-presence-monitor")
        self._thread.start()

    def stop(self, join_timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self.interval)
            if self._stop_event.is_set():
                break
            try:
                self.poll_once()
            except Exception as e:
                self.logger.error(f"Device presence poll failed: {e}", exc_info=True)

    def poll_once(self) -> None:
        """One presence check + reconciliation. Public so tests can call it
        directly without spinning up the sleep loop."""
        current = device_registry.present_device_ids(self.config_dir)
        appeared = current - self._present
        disappeared = self._present - current
        if not appeared and not disappeared:
            return
        for device_id in disappeared:
            self.logger.info(f"Device no longer detected: {device_id}")
            self.controller.remove_device_engine(device_id)
        for device_id in appeared:
            self.logger.info(f"Device detected: {device_id}")
            self.controller.add_device_engine(device_id)
        self._present = current
        if self.event_bus is not None:
            entries = [e for e in device_registry.list_devices(self.config_dir)
                      if e.get("id") in current]
            self.event_bus.publish(Topic.DEVICES_CHANGED, entries)
