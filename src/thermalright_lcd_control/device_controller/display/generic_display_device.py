# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""GenericDisplayDevice — a single data-driven device that wires together the
image encoder, the header builder and the transport. A new device is described
by a DeviceDescriptor (no per-device subclass needed)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import usb.core
import usb.util

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.device_controller.display.config_loader import ConfigLoader
from thermalright_lcd_control.device_controller.display.device_config import resolve_active_config
from thermalright_lcd_control.device_controller.display.event_bus import Topic
from thermalright_lcd_control.device_controller.display.frame_cache import FrameEncodeCache
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator
from thermalright_lcd_control.device_controller.display.header import HeaderBuilder
from thermalright_lcd_control.device_controller.display.image_encoder import (
    ImageEncoder,
    ImageEncoding,
)
from thermalright_lcd_control.device_controller.display.transport import Transport, TransportType
from thermalright_lcd_control.device_controller.display.utils import trim_native_heap


@dataclass
class DeviceDescriptor:
    """Everything needed to drive a device, as data."""
    id: str
    vid: int
    pid: int
    width: int
    height: int
    transport: TransportType
    chunk_size: int
    encoding: ImageEncoding
    generic: bool = True
    header: HeaderBuilder = field(default_factory=lambda: HeaderBuilder.static(b""))
    report_id: bytes = b"\x00"
    cmd: int = 0
    command: int = 0xF5
    jpeg_quality: int = 85
    ep_in: int = 0x81
    start_wait: float = 0.0


def _find_bulk_out_ep(dev: usb.core.Device) -> tuple[int, int]:
    """
    Return (interface_number, ep_out_address) for the first interface that exposes a BULK OUT endpoint.
    Prefer vendor-specific interfaces (class 255) if present.
    """
    dev.set_configuration()
    cfg = dev.get_active_configuration()

    for intf in cfg:
        if intf.bInterfaceClass == 255:
            for ep in intf:
                if (usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT and
                        usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK):
                    return intf.bInterfaceNumber, ep.bEndpointAddress

    for intf in cfg:
        for ep in intf:
            if (usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT and
                    usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK):
                return intf.bInterfaceNumber, ep.bEndpointAddress

    raise RuntimeError("No BULK OUT endpoint found on this USB device")


class GenericDisplayDevice:
    """Data-driven display device: encoder + header + transport + cached loop."""

    def __init__(self, descriptor: DeviceDescriptor, config_dir: str,
                 build_generator: bool = True):
        self.d = descriptor
        self.width = descriptor.width
        self.height = descriptor.height
        self.logger = LoggerConfig.setup_service_logger()

        self.config_file = str(resolve_active_config(
            config_dir, self.d.id, self.width, self.height))

        self._stop_event = threading.Event()
        self._reload_requested = threading.Event()
        self._pending_config = None
        self._reload_id = str(self.d.id)
        self._event_bus = None
        self._encode_cache = FrameEncodeCache()

        self._dev = None
        self._iface: int | None = None
        self.transport = self._open_transport()
        if descriptor.start_wait > 0:
            time.sleep(descriptor.start_wait)

    # --- device opening ---

    def _open_transport(self) -> Transport:
        d = self.d
        if d.transport == TransportType.HID:
            import hid
            self._dev = hid.Device(d.vid, d.pid)
            return Transport.create(d.transport, self._dev, d.chunk_size,
                                    report_id=d.report_id)

        self._dev = usb.core.find(idVendor=d.vid, idProduct=d.pid)
        if self._dev is None:
            raise RuntimeError(f"USB device {d.vid:04x}:{d.pid:04x} not found")
        try:
            for intf in self._dev.get_active_configuration():
                if self._dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    self._dev.detach_kernel_driver(intf.bInterfaceNumber)
        except (NotImplementedError, usb.core.USBError) as e:
            self.logger.debug(f"Could not detach kernel driver for {d.vid:04x}:{d.pid:04x}: {e}")
        self._iface, ep_out = _find_bulk_out_ep(self._dev)
        usb.util.claim_interface(self._dev, self._iface)
        return Transport.create(d.transport, self._dev, d.chunk_size,
                                ep_out=ep_out, ep_in=d.ep_in, command=d.command,
                                pid=d.pid)

    def attach_event_bus(self, event_bus, device_id: str) -> None:
        self._reload_id = str(device_id)
        self._event_bus = event_bus
        event_bus.subscribe(Topic.CONFIG_RELOAD, self._on_config_reload)

    def _on_config_reload(self, device_id, config=None) -> None:
        if str(device_id) == self._reload_id:
            self._pending_config = config
            self._reload_requested.set()

    # --- frame assembly ---

    def _build_frame(self, img) -> bytes:
        d = self.d
        payload = ImageEncoder.encode(img, d.encoding, self.width, self.height,
                                      jpeg_quality=d.jpeg_quality)
        header = d.header.build(self.width, self.height,
                                payload_size=len(payload), cmd=d.cmd)
        return header + payload

    def send(self, frame_idx: int) -> bool:
        """Send the already-encoded frame for ``frame_idx`` from cache.

        Returns ``False`` when the frame is not yet cached (encode pass not
        completed yet), so the RenderEngine can decide to skip or wait."""
        frame = self._encode_cache.get(frame_idx)
        if frame is None:
            return False
        self.transport.send(frame)
        return True

    def encode_and_cache_frame(self, frame_idx: int, img) -> None:
        """Encode ``img`` and store it in the cache under ``frame_idx``.

        Called by RenderEngine from its background encode thread whenever
        metrics change, so all frames are pre-encoded before the render loop
        needs them."""
        frame = self._build_frame(img)
        self._encode_cache.store(frame_idx, frame)

    def invalidate_cache(self) -> None:
        """Drop cached encoded frames (called when the engine rebuilds the
        generator, so the device stops sending the previous config)."""
        self._encode_cache.clear()

    def set_frame_count(self, n_frames: int) -> None:
        self._encode_cache.set_frame_count(n_frames)

    def stop(self):
        self._stop_event.set()

    def close(self):
        self.stop()
        if self._event_bus is not None:
            self._event_bus.unsubscribe(Topic.CONFIG_RELOAD, self._on_config_reload)
        try:
            if self._iface is not None and self._dev is not None:
                usb.util.release_interface(self._dev, self._iface)
                usb.util.dispose_resources(self._dev)
        except Exception as e:
            self.logger.debug(f"Error releasing USB resources on close: {e}")

