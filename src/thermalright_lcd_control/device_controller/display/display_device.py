# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import pathlib
import struct
import time
from abc import abstractmethod, ABC
from typing import Optional

import hid
import usb
from PIL import Image

from .config_loader import ConfigLoader
from .generator import DisplayGenerator
from ...common.logging_config import LoggerConfig


class DisplayDevice(hid.Device, ABC):
    _generator: DisplayGenerator = None

    def __init__(self, vid, pid, chunk_size, width, height, config_file: str, *args, **kwargs):
        super().__init__(vid, pid)
        self.vid = vid
        self.pid = pid
        self.chunk_size = chunk_size
        self.height = height
        self.width = width
        self.header = self.get_header()
        self.config_file = config_file
        self.last_modified = pathlib.Path(config_file).stat().st_mtime_ns
        self.logger = self.logger = LoggerConfig.setup_service_logger()
        self._build_generator()
        self.logger.debug(f"DisplayDevice initialized with header: {self.header}")

    def _build_generator(self) -> DisplayGenerator:
        config_loader = ConfigLoader()
        config = config_loader.load_config(self.config_file)
        config.output_width = self.width
        config.output_height = self.height
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


class DisplayDevice04185303(DisplayDevice):
    def __init__(self, config_file: str):
        super().__init__(0x0418, 0x5303, 64, 320, 320, config_file)

    def get_header(self) -> bytes:
        return struct.pack('<BBHHH',
                           0x69,
                           0x88,
                           320,
                           320,
                           0
                           )


class DisplayDevice04185304(DisplayDevice):
    def __init__(self, config_file: str):
        super().__init__(0x0418, 0x5304, 512, 480, 480, config_file)

    def get_header(self) -> bytes:
        return struct.pack('<BBHHH',
                           0x69,
                           0x88,
                           480,
                           480,
                           0
                           )


class DisplayDevice04168001(DisplayDevice):
    def __init__(self, config_file: str):
        super().__init__(0x0416, 0x8001, 64, 480, 480, config_file)

    def get_header(self) -> bytes:
        prefix = bytes([0xDA, 0xDB, 0xDC, 0xDD])
        body = struct.pack('<6HIH',
                           2,
                           1,
                           480,
                           480,
                           2,
                           0,
                           460800,
                           0
                           )
        return prefix + body


class DisplayDevice04165302(DisplayDevice):
    def __init__(self, config_file: str):
        super().__init__(0x0416, 0x5302, 512, 320, 240, config_file)

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


def load_device(config_file: str) -> Optional[DisplayDevice]:
    try:
        for device in hid.enumerate():
            if device['vendor_id'] == 0x0416:
                if device['product_id'] == 0x5302:
                    return DisplayDevice04165302(config_file)
                elif device['product_id'] == 0x8001:
                    return DisplayDevice04168001(config_file)
            elif device['vendor_id'] == 0x0418:
                if device['product_id'] == 0x5303:
                    return DisplayDevice04185303(config_file)
                elif device['product_id'] == 0x5304:
                    return DisplayDevice04185304(config_file)
    except Exception as e:
        raise Exception(f"No supported device found: {e}") from e
