# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import usb.core
import usb.util
import pathlib
import struct
import time
from abc import abstractmethod, ABC
from .frozen_warframe_lcd import FrozenWarframeLCD
from typing import Optional

import hid
import usb
from PIL import Image

from .config_loader import ConfigLoader
from .generator import DisplayGenerator
from ...common.logging_config import LoggerConfig


class DisplayDevice(hid.Device, ABC):
    _generator: DisplayGenerator = None

    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, *args, **kwargs):
        super().__init__(vid, pid)
        self.vid = vid
        self.pid = pid
        self.chunk_size = chunk_size
        self.height = height
        self.width = width
        self.header = self.get_header()
        self.config_file = f"{config_dir}/config_{width}{height}.yaml"
        self.last_modified = pathlib.Path(self.config_file).stat().st_mtime_ns
        self.logger = self.logger = LoggerConfig.setup_service_logger()
        self._build_generator()
        self.logger.debug(f"DisplayDevice initialized with header: {self.header}")

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

    def _encode_image(self,img: Image) -> bytearray:
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
            frame_packets.append(bytes([0x00]) + chunk)
        return frame_packets

    def run(self):
        self.logger.info("Display device running")
        while True:
            img, delay_time = self._get_generator().get_frame_with_duration()
            header = self.get_header()
            img_bytes = header + self._encode_image(img)
            frame_packets = self._prepare_frame_packets(img_bytes)
            for packet in frame_packets:
                self.write(packet)
            time.sleep(delay_time)


class DisplayDevice04185304(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0418, 0x5304, 512, 480, 480, config_dir)

    def get_header(self) -> bytes:
        return struct.pack('<BBHHH',
                           0x69,
                           0x88,
                           480,
                           480,
                           0
                           )


class DisplayDevice04165302(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0416, 0x5302, 512, 320, 240, config_dir)

    def get_header(self) -> bytes:
        prefix = bytes([0xDA, 0xDB, 0xDC, 0xDD])
        body = struct.pack(
            '<6HIH',
            2,
            1,
            320,
            240,
            2,
            0,
            153600,
            0
        )
        return prefix + body



def load_device(config_dir: str) -> Optional[DisplayDevice]:
    try:
        # Primary detection via HID
        for device in hid.enumerate():
            if device['vendor_id'] == 0x0402 and device['product_id'] == 0x3922:
                return FrozenWarframeLCD(config_dir)

            if device['vendor_id'] == 0x0416:
                if device['product_id'] == 0x5302:
                    return DisplayDevice04165302(config_dir)
                elif device['product_id'] == 0x8001:
                    return DisplayDevice04168001(config_dir)
            elif device['vendor_id'] == 0x0418:
                if device['product_id'] == 0x5303:
                    return DisplayDevice04185303(config_dir)
                elif device['product_id'] == 0x5304:
                    return DisplayDevice04185304(config_dir)
            elif device['vendor_id'] == 0x87ad:
                if device['product_id'] == 0x70db:
                    return DisplayDevice087ad070db(config_dir)

        # Fallback detection via pyusb
        dev = usb.core.find(idVendor=0x0402, idProduct=0x3922)
        if dev:
            return FrozenWarframeLCD(config_dir)

        raise Exception("No supported device found")

    except Exception as e:
        raise Exception(f"Device detection failed: {e}") from e

