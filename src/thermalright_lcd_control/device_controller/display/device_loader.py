# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Unified device loader.

One ``device_<id>.yaml`` file per device drives the stack. Each entry carries a
``generic`` flag (default ``True``):

* ``generic: true``  → data-driven :class:`GenericDisplayDevice`.
* ``generic: false`` → the legacy class stack, resolved from (vid, pid, width,
  height) via :func:`find_legacy_class`.

Both kinds run, each in its own thread, and share the active-config keying by
device id (``config_<id>.yaml``). This is the composition root: it is the only
place that knows about both the generic and the legacy stacks; neither imports
the other.
"""
from __future__ import annotations

import threading
from pathlib import Path

import usb.core
import yaml

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.common.supported_devices import find_legacy_class
from thermalright_lcd_control.device_controller.display.device_config import (
    resolve_active_config,
)
from thermalright_lcd_control.device_controller.display.device_registry import (
    list_devices,
    register_detected_devices,
    write_device_entry,
)
from thermalright_lcd_control.device_controller.display.generic_device_loader import (
    _as_int,
    build_generic_device,
)
from thermalright_lcd_control.device_controller.display.render_engine import RenderEngine


def build_legacy_device(entry: dict, config_dir: str):
    """Instantiate a legacy device from one ``devices.yaml`` entry.

    The class is resolved by (vid, pid, width, height) so ChiZhu's same-VID:PID
    variants stay distinct. The active config path is id-keyed (seeded from the
    resolution-keyed file) and injected into the constructor.
    """
    vid, pid = _as_int(entry["vid"]), _as_int(entry["pid"])
    width, height = int(entry["width"]), int(entry["height"])
    device_id = str(entry.get("id") or f"{pid:04x}_{vid:04x}")

    cls = find_legacy_class(vid, pid, width, height)
    if cls is None:
        raise ValueError(
            f"No legacy device class for {vid:04x}:{pid:04x} {width}x{height} "
            f"(id={device_id})")

    config_file = resolve_active_config(config_dir, device_id, width, height)
    device = cls(config_dir, config_file=str(config_file))
    # The leaf legacy classes hard-code their __init__ signature and cannot accept
    # build_generator=False, so drop the device's own generator after construction:
    # in the GUI path the RenderEngine owns the generator and the device is a pure
    # send_image sink. Frees the legacy generator's metrics thread / preloaded
    # frames. Standalone service builds legacy devices directly (not via here).
    gen = getattr(device, "_generator", None)
    if gen is not None:
        gen.cleanup()
        device._generator = None
    return device


class DeviceLoader:
    """Read the per-device ``device_<id>.yaml`` files and run each in a thread."""

    def __init__(self, config_dir: str, event_bus=None, active_device_id=None,
                 media_active: bool = True, media_endpoint: str | None = None):
        self.config_dir = config_dir
        self.event_bus = event_bus
        self.active_device_id = str(active_device_id) if active_device_id else None
        # Window visibility: combined with the active device id so only the
        # previewed device's engine preloads its media; the others start in
        # low-memory mode (encoded cache + on-demand decode).
        self.media_active = bool(media_active)
        # Configured bundled-video download host, forwarded to each engine's
        # FrameManager (None → the engine's public default).
        self.media_endpoint = media_endpoint
        self.logger = LoggerConfig.setup_service_logger()
        self._active: dict[str, tuple] = {}

    # --- config reading ---

    def load_entries(self) -> list[dict]:
        """Return the entries from every ``device_<id>.yaml`` (``[]`` if none)."""
        return list_devices(self.config_dir)

    def migrate_device_info(self) -> None:
        """Migrate a legacy ``devices.yaml`` registry to per-device files.

        Runs only when no ``device_<id>.yaml`` file is present, and only splits an
        existing single-file ``devices.yaml`` registry into one file per device.

        It no longer auto-creates a device from bundled profiles: when nothing
        is configured the GUI opens its device configuration page so the user
        adds a device explicitly.
        """
        if self.load_entries():
            return
        self._split_legacy_registry()

    def autodetect_devices(self) -> list[str]:
        """Probe-register connected known devices that aren't configured yet.

        trcc-style zero-touch startup: the probe registry says which handshake
        each connected VID:PID speaks, the device's answer says which screen it
        drives, and the resulting entry lands as a normal ``device_<id>.yaml``.
        Already-configured (vid, pid) pairs are never touched. Best-effort: any
        failure leaves the manual add flow as the fallback.
        """
        try:
            added = register_detected_devices(self.config_dir)
        except Exception as e:
            self.logger.error(f"Device auto-detection failed: {e}", exc_info=True)
            return []
        for entry in added:
            self.logger.info(
                f"Auto-registered detected device {entry['id']} "
                f"({entry['vid']}:{entry['pid']} {entry['width']}x{entry['height']}, "
                f"{entry['transport']}/{entry['encoding']})")
        return [entry["id"] for entry in added]

    def _split_legacy_registry(self) -> bool:
        """Split a legacy single-file ``devices.yaml`` into per-device files.

        Returns ``True`` if a registry was found and split (the old file is then
        renamed to ``devices.yaml.bak``), ``False`` otherwise.
        """
        legacy = Path(self.config_dir) / "devices.yaml"
        try:
            data = yaml.safe_load(legacy.read_text())
        except FileNotFoundError:
            return False
        entries = [e for e in (data or {}).get("devices") or [] if isinstance(e, dict)]
        if not entries:
            return False

        written: list[str] = []
        for entry in entries:
            if entry.get("id") is None:
                continue
            entry["id"] = str(entry["id"])
            try:
                write_device_entry(self.config_dir, entry)
                written.append(entry["id"])
            except ValueError:
                pass  # a device file for that id already exists; leave it
        legacy.rename(legacy.with_suffix(".yaml.bak"))
        self.logger.info(
            f"Split legacy devices.yaml into per-device files: {', '.join(written)}")
        return True

    # --- lifecycle ---

    def start_all(self) -> list:
        """Build one RenderEngine per configured entry that is currently
        present and start each in its own thread. An absent device gets no
        engine at all — active or not."""
        for entry in self.load_entries():
            self._start_one(entry)
        return self.active_engines()

    def start_one(self, device_id: str):
        """Build+start the engine for a single already-configured entry, if
        it is currently present. No-op (returns ``None``) when the entry is
        missing or the device isn't plugged in. Idempotent: a device that
        already has a running engine is returned as-is."""
        entry = next((e for e in self.load_entries()
                     if str(e.get("id")) == str(device_id)), None)
        if entry is None:
            self.logger.warning(f"start_one: no entry for {device_id}")
            return None
        return self._start_one(entry)

    def stop_one(self, device_id: str, join_timeout: float = 2.0) -> None:
        """Stop, join and close a single running engine (if any), releasing
        its DisplayGenerator. No-op if that device has no running engine."""
        pair = self._active.pop(str(device_id), None)
        if pair is None:
            return
        engine, thread = pair
        engine.stop()
        thread.join(timeout=join_timeout)
        close = getattr(engine, "close", None)
        if callable(close):
            try:
                close()
            except Exception as e:
                self.logger.debug(f"Error closing device: {e}")

    def active_engines(self) -> list:
        """Currently running engines, read live from the tracking dict."""
        return [engine for engine, _ in self._active.values()]

    def stop_all(self, join_timeout: float = 2.0) -> None:
        for device_id in list(self._active):
            self.stop_one(device_id, join_timeout=join_timeout)

    def _start_one(self, entry: dict):
        """Build+start one entry's engine if present; returns the engine, or
        ``None`` (malformed entry, absent device, or build failure)."""
        try:
            vid, pid = _as_int(entry["vid"]), _as_int(entry["pid"])
            width, height = int(entry["width"]), int(entry["height"])
        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(f"Skipping malformed device entry: {e}")
            return None

        device_id = str(entry.get("id") or f"{pid:04x}_{vid:04x}")
        if device_id in self._active:
            return self._active[device_id][0]     # already running

        present = usb.core.find(idVendor=vid, idProduct=pid) is not None
        if not present:
            self.logger.info(f"Device {vid:04x}:{pid:04x} absent; no engine")
            return None

        generic = bool(entry.get("generic", True))
        try:
            if generic:
                sink = build_generic_device(entry, self.config_dir)
            else:
                sink = build_legacy_device(entry, self.config_dir)
                self._reset(sink)
        except Exception as e:
            # last-resort: a single device failing to open must not abort
            # loading the others (HID/USB/SCSI errors are heterogeneous).
            self.logger.error(f"Failed to open {vid:04x}:{pid:04x}: {e}",
                              exc_info=True)
            return None

        try:
            config_file = str(resolve_active_config(
                self.config_dir, device_id, width, height))
            # Only the previewed device preloads its decoded media; when no
            # active id is known (standalone), every engine preloads.
            media_active = self.media_active and (
                self.active_device_id is None
                or device_id == self.active_device_id)
            engine_kwargs = {"sink": sink, "media_active": media_active}
            if self.media_endpoint:
                engine_kwargs["media_endpoint"] = self.media_endpoint
            engine = RenderEngine(width, height, config_file, device_id,
                                  **engine_kwargs)
        except Exception as e:
            self.logger.error(f"Failed to build engine for {device_id}: {e}",
                              exc_info=True)
            return None

        if self.event_bus is not None:
            engine.attach_event_bus(self.event_bus, device_id)

        thread = threading.Thread(
            target=engine.run, daemon=True, name=f"render-{device_id}")
        thread.start()
        self._active[device_id] = (engine, thread)
        self.logger.info(f"Started engine {device_id} (with device)")
        return engine

    def _reset(self, device) -> None:
        """USB-reset a freshly opened legacy device (parity with old flow)."""
        reset = getattr(device, "reset", None)
        if callable(reset):
            try:
                reset()
            except Exception as e:
                self.logger.warning(f"Device reset failed: {e}")
