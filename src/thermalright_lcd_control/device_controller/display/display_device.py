# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import threading
from abc import ABC, abstractmethod

import pyvips
import usb

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.device_controller.display.event_bus import Topic
from thermalright_lcd_control.device_controller.display.frame_cache import FrameEncodeCache
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator
from thermalright_lcd_control.device_controller.display.image_encoder import (
    encode_rgb565_le_columns,
)


class DisplayDevice(ABC):
    _generator: DisplayGenerator = None
    dev = None
    report_id = bytes([0x00])
    vid = None
    pid = None
    width = None
    height = None
    mode = None

    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, *args,
                 config_file: str = None, **kwargs):
        self.vid = vid
        self.pid = pid
        self.height = height
        self.width = width
        self.chunk_size = chunk_size
        self.header = self.get_header()
        self.config_file = config_file or f"{config_dir}/config_{width}{height}.yaml"
        self.logger = LoggerConfig.setup_service_logger()
        self._stop_event = threading.Event()
        self._reload_requested = threading.Event()
        self._pending_config = None
        self._reload_id = f"{pid}_{vid}"
        self._event_bus = None
        self._encode_cache = FrameEncodeCache()
        self.logger.debug(f"DisplayDevice initialized with header: {self.header}")

    def __getitem__(self, __name):
        return self.__getattribute__(__name)

    def __str__(self):
        return f"VID: {self.vid}, PID: {self.pid} ({self.width}x{self.height})"

    def attach_event_bus(self, event_bus, device_id: str) -> None:
        self._reload_id = str(device_id)
        self._event_bus = event_bus
        event_bus.subscribe(Topic.CONFIG_RELOAD, self._on_config_reload)

    def _on_config_reload(self, device_id, config=None) -> None:
        if str(device_id) == self._reload_id:
            self._pending_config = config
            self._reload_requested.set()

    def _encode_image(self, img: pyvips.Image) -> bytearray:
        return bytearray(encode_rgb565_le_columns(img, self.width, self.height))

    def send(self, frame_idx: int) -> bool:
        """Send the already-encoded frame for ``frame_idx`` from cache.

        Returns ``False`` when the frame is not yet cached (encode pass not
        completed yet), so the RenderEngine can decide to skip or wait."""
        img_bytes = self._encode_cache.get(frame_idx)
        if img_bytes is None:
            return False
        for packet in self._prepare_frame_packets(img_bytes):
            self.send_packet(packet)
        return True

    def encode_and_cache_frame(self, frame_idx: int, img: pyvips.Image) -> None:
        """Encode ``img`` and store it in the cache under ``frame_idx``.

        Called by RenderEngine from its background encode thread whenever
        metrics change, so all frames are pre-encoded before the render loop
        needs them."""
        img_bytes = self.header + self._encode_image(img)
        self._encode_cache.store(frame_idx, img_bytes)

    def invalidate_cache(self) -> None:
        """Drop cached encoded frames (called when the engine rebuilds the
        generator, so the device stops sending the previous config)."""
        self._encode_cache.clear()

    def set_frame_count(self, n_frames: int) -> None:
        self._encode_cache.set_frame_count(n_frames)

    @abstractmethod
    def get_header(self, *args, **kwargs):
        pass

    def reset(self):
        dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
        if dev is None:
            raise ValueError("Display device not found")
        dev.reset()
        self.logger.info("Display device reinitialised via USB reset")

    def _prepare_frame_packets(self, img_bytes: bytes):
        frame_packets = []
        for i in range(0, len(img_bytes), self.chunk_size):
            chunk = img_bytes[i:i + self.chunk_size]
            if len(chunk) < self.chunk_size:
                chunk += b"\x00" * (self.chunk_size - len(chunk))
            frame_packets.append(self.report_id + chunk)
        return frame_packets

    def stop(self):
        """Signal the display loop to stop. Safe to call from a signal handler."""
        self._stop_event.set()
        if getattr(self, "_event_bus", None) is not None:
            self._event_bus.unsubscribe(Topic.CONFIG_RELOAD, self._on_config_reload)

    @abstractmethod
    def send_packet(self, packet: bytes):
        pass

    def get(self, __name, default=None):
        return self.__dict__.get(__name, default)

    @staticmethod
    def info() -> dict:
        pass