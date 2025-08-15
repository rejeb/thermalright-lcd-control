# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import pathlib
import struct
from abc import abstractmethod, ABC
from typing import Optional
import time

import usb
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config_loader import ConfigLoader
from .generator import DisplayGenerator
from ...common.logging_config import LoggerConfig


class DisplayDevice(ABC):
    _generator: DisplayGenerator = None

    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, config_file: Optional[str] = None):
        self.vid = vid
        self.pid = pid
        self.chunk_size = chunk_size
        self.height = height
        self.width = width
        self.header = self.get_header()
        self.config_file = config_file or f"{config_dir}/device_config.yaml"
        self.last_modified = pathlib.Path(self.config_file).stat().st_mtime_ns
        self.logger = LoggerConfig.setup_service_logger()
        self._build_generator()
        self.dev = None  # USB device will be initialized later
        self.logger.debug(f"{self} initialized with header: {self.header}")

    def __str__(self):
        return f"DisplayDevice(vid=0x{self.vid:04X}, pid=0x{self.pid:04X}, size={self.width}x{self.height})"

    def _build_generator(self) -> DisplayGenerator:
        config_loader = ConfigLoader()
        config = config_loader.load_config(self.config_file, self.width, self.height)
        self._generator = DisplayGenerator(config)
        return self._generator

    def _get_generator(self) -> DisplayGenerator:
        if self._generator is None:
            self.logger.info(f"No generator found, reloading from {self.config_file}")
            return self._build_generator()
        elif pathlib.Path(self.config_file).stat().st_mtime_ns > self.last_modified:
            self.logger.info(f"Config file updated: {self.config_file}")
            self.last_modified = pathlib.Path(self.config_file).stat().st_mtime_ns
            return self._build_generator()
        else:
            return self._generator

    def _encode_image(self, img: Image) -> bytearray:
        width, height = img.size
        pixels = np.array(img.convert("RGB")).reshape((height, width, 3))
        r = (pixels[:, :, 0] & 0xF8) << 8
        g = (pixels[:, :, 1] & 0xFC) << 3
        b = (pixels[:, :, 2] >> 3)
        val565 = r | g | b
        lo = val565 & 0xFF
        hi = (val565 >> 8) & 0xFF
        out = bytearray()

        for i in range(width * height):
            if i % height == 0:
                out.extend((0x00, 0x00))
            else:
                out.extend((lo.flat[i], hi.flat[i]))

        return out

    @abstractmethod
    def get_header(self, *args, **kwargs) -> bytes:
        pass

    def initialize_device(self):
        self.logger.info(f"Searching for device VID={hex(self.vid)}, PID={hex(self.pid)}")
        self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
        if self.dev is None:
            self.logger.warning(f"{self} not found")
            return False

        try:
            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0, 0)]

            if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                self.logger.debug(f"Detaching kernel driver from interface {intf.bInterfaceNumber}")
                self.dev.detach_kernel_driver(intf.bInterfaceNumber)

            usb.util.claim_interface(self.dev, intf.bInterfaceNumber)
            self.logger.info(f"{self} successfully initialized")
            return True
        except usb.core.USBError as e:
            self.logger.error(f"USBError during device initialization: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Unexpected error during device initialization: {e}", exc_info=True)
        finally:
            if self.dev:
                try:
                    cfg = self.dev.get_active_configuration()
                    intf = cfg[(0, 0)]
                    usb.util.release_interface(self.dev, intf.bInterfaceNumber)
                    self.logger.debug("Released USB interface")
                except Exception as e:
                    self.logger.warning(f"Failed to release interface: {e}")
        return False

    def write(self, packet: bytes):
        if self.dev is None:
            raise ValueError(f"{self} not initialized")

        try:
            self.logger.debug(f"Sending packet (size: {len(packet)}) to EP 2 OUT")
            bytes_written = self.dev.write(0x02, packet)
            self.logger.debug(f"Written {bytes_written} bytes to device")

            self.logger.debug("Reading response from EP 1 IN")
            response = self.dev.read(0x81, self.chunk_size)
            self.logger.debug(f"Received response: {response}")
        except usb.core.USBError as e:
            self.logger.error(f"USBError during write operation: {e}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during write operation: {e}", exc_info=True)
            raise
        finally:
            try:
                cfg = self.dev.get_active_configuration()
                intf = cfg[(0, 0)]
                usb.util.release_interface(self.dev, intf.bInterfaceNumber)
                self.logger.debug("Released USB interface")
            except Exception as e:
                self.logger.warning(f"Failed to release interface: {e}")

    def reset(self):
        if self.dev is None:
            raise ValueError(f"{self} not initialized")
        self.dev.reset()
        self.logger.info(f"{self} reinitialised via USB reset")

    def _prepare_frame_packets(self, img_bytes: bytes):
        frame_packets = []
        for i in range(0, len(img_bytes), self.chunk_size):
            chunk = img_bytes[i:i + self.chunk_size]
            if len(chunk) < self.chunk_size:
                chunk += b"\x00" * (self.chunk_size - len(chunk))
            frame_packets.append(bytes([0x00]) + chunk)
        return frame_packets

    def run(self):
        self.logger.info(f"{self} running")
        while True:
            try:
                img, delay_time = self._get_generator().get_frame_with_duration()
                header = self.get_header()
                img_bytes = header + self._encode_image(img)
                frame_packets = self._prepare_frame_packets(img_bytes)

                for packet in frame_packets:
                    self.logger.debug(f"Sending packet of size {len(packet)}")
                    self.write(packet)

                time.sleep(delay_time)

            except Exception as e:
                self.logger.error(f"Error in display run loop: {e}")
                break

# Subclasses for specific devices
class DisplayDevice04185303(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0418, 0x5303, 64, 320, 320, config_dir)

    def get_header(self) -> bytes:
        return struct.pack('<BBHHH', 0x69, 0x88, 320, 320, 0)


class DisplayDevice04185304(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0418, 0x5304, 512, 480, 480, config_dir)

    def get_header(self) -> bytes:
        return struct.pack('<BBHHH', 0x69, 0x88, 480, 480, 0)


class DisplayDevice04168001(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0416, 0x8001, 64, 480, 480, config_dir)

    def get_header(self) -> bytes:
        prefix = bytes([0xDA, 0xDB, 0xDC, 0xDD])
        body = struct.pack('<6HIH', 2, 1, 480, 480, 2, 0, 460800, 0)
        return prefix + body


class DisplayDevice04165302(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0416, 0x5302, 512, 320, 240, config_dir)

    def get_header(self) -> bytes:
        prefix = bytes([0xDA, 0xDB, 0xDC, 0xDD])
        body = struct.pack('<6HIH', 2, 1, 320, 240, 2, 0, 153600, 0)
        return prefix + body


class DisplayDevice04023922(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0402, 0x3922, 512, 240, 240, config_dir)
        self.supported_formats = {
            57600: ("RGB565", (240, 240)),
            38400: ("GRAY8", (240, 160)),
            28800: ("GRAY8", (240, 120)),
        }

    def get_header(self) -> bytes:
        prefix = bytes([0xDA, 0xDB, 0xDC, 0xDD])
        body = struct.pack('<6HIH', 2, 1, 240, 240, 2, 0, 57600, 0)
        return prefix + body

    def identify_frame_format(self, payload: bytes):
        size = len(payload)
        if size in self.supported_formats:
            return self.supported_formats[size]
        raise ValueError(f"Unknown payload size: {size}")

    def decode_frame(self, payload: bytes):
        fmt, shape = self.identify_frame_format(payload)
        if fmt == "RGB565":
            arr = np.frombuffer(payload, dtype=np.uint16).reshape(shape)
            r = ((arr >> 11) & 0x1F) << 3
            g = ((arr >> 5) & 0x3F) << 2
            b = (arr & 0x1F) << 3
            rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
            return Image.fromarray(rgb, "RGB")
        elif fmt == "GRAY8":
            arr = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            return Image.fromarray(arr)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    def visualize(self, payload: bytes, annotate: bool = False, label: str = ""):
        img = self.decode_frame(payload)
        if annotate:
            draw = ImageDraw.Draw(img.convert("RGB"))
            font = ImageFont.load_default()
            draw.text((5, 5), label, fill=(255, 255, 255), font=font)
        return img

    def entropy(self, payload: bytes):
        img = self.decode_frame(payload)
        arr = np.array(img.convert("L")).ravel()
        hist = np.histogram(arr, bins=256, range=(0, 255))[0]
        prob = hist / np.sum(hist)
        prob = prob[prob > 0]
        return round(-np.sum(prob * np.log2(prob)), 2)


DEVICE_CLASSES = {
    (0x0418, 0x5303): DisplayDevice04185303,
    (0x0418, 0x5304): DisplayDevice04185304,
    (0x0416, 0x8001): DisplayDevice04168001,
    (0x0416, 0x5302): DisplayDevice04165302,
    (0x0402, 0x3922): DisplayDevice04023922,
}
