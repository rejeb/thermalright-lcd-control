# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import pathlib
import time
from abc import abstractmethod, ABC

import usb
from PIL import Image

from .config_loader import ConfigLoader
from .generator import DisplayGenerator
from ...common.logging_config import LoggerConfig


class DisplayDevice(ABC):
    _generator: DisplayGenerator = None
    dev = None
    report_id = bytes([0x00])
    vid = None
    pid = None
    width = None
    height = None

    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, *args, **kwargs):
        self.vid = vid
        self.pid = pid
        self.height = height
        self.width = width
        self.chunk_size = chunk_size
        self.header = self.get_header()
        self.config_file = f"{config_dir}/config_{width}{height}.yaml"
        self.last_modified = pathlib.Path(self.config_file).stat().st_mtime_ns
        self.logger = self.logger = LoggerConfig.setup_service_logger()
        self._generator = self._build_generator()
        self.logger.debug(f"DisplayDevice initialized with header: {self.header}")

    def __getitem__(self, __name):
        return self.__getattribute__(__name)

    def __str__(self):
        return f"VID: {self.vid}, PID: {self.pid} ({self.width}x{self.height})"

    def _build_generator(self) -> DisplayGenerator:
        config_loader = ConfigLoader()
        config = config_loader.load_config(self.config_file, self.width, self.height)
        return DisplayGenerator(config)

    def _get_generator(self) -> DisplayGenerator:
        if self._generator is None:
            self.logger.info(f"No generator found, reloading from {self.config_file}")
            self._generator = self._build_generator()
            return self._generator
        elif pathlib.Path(self.config_file).stat().st_mtime_ns > self.last_modified:
            self.logger.info(f"Config file updated: {self.config_file}")
            self.last_modified = pathlib.Path(self.config_file).stat().st_mtime_ns
            self._generator = self._build_generator()
            self.logger.info(f"Display device generator reloaded from {self.config_file}")
            return self._generator
        else:
            return self._generator

    def _encode_image(self, img: Image) -> bytearray:
        width, height = img.size

        coords = [(x, y) for x in range(width) for y in range(height - 1, -1, -1)]

        out = bytearray()

        for i, (x, y) in enumerate(coords, start=1):
            if i % height == 0:
                out.extend((0x00, 0x00))
            else:
                r, g, b = img.getpixel((x, y))
                val565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                lo = val565 & 0xFF
                hi = (val565 >> 8) & 0xFF
                out.extend((lo, hi))

        return out

    @abstractmethod
    def get_header(self, *args, **kwargs):
        pass

    def reset(self):
        # Find device (ex. Winbond 0416:5302)
        dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
        if dev is None:
            raise ValueError("Display device not found")

        # Reset USB device
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

    def run(self):
        self.logger.info("Display device running")
        while True:
            img, delay_time = self._get_generator().get_frame_with_duration()
            header = self.get_header()
            img_bytes = header + self._encode_image(img)
            frame_packets = self._prepare_frame_packets(img_bytes)
            for packet in frame_packets:
                self.send_packet(packet)
            time.sleep(delay_time)

    @abstractmethod
    def send_packet(self, packet: bytes):
        pass

    def get(self, __name, default=None):
        return self.__dict__.get(__name, default)

    @staticmethod
    def info() -> dict:
        pass
