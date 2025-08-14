# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import pathlib
import struct
import time
from abc import abstractmethod, ABC
from typing import Optional

import usb
from PIL import Image

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
    def get_header(self, *args, **kwargs) -> bytes:
        pass

    def write(self, packet: bytes):
        dev = self.dev
        if dev is None:
            self.logger.error(f"{self} not found during write()")
            raise ValueError(f"{self} not found")

        try:
            dev.set_configuration()
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]

            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)
                self.logger.info(f"Detached kernel driver from interface {intf.bInterfaceNumber}")

            usb.util.claim_interface(dev, intf.bInterfaceNumber)
            self.logger.debug(f"Interface {intf.bInterfaceNumber} claimed")

            dev.write(2, packet)  # EP 2 OUT
        except Exception as e:
            self.logger.error(f"Failed to write packet to {self}: {e}")

    def reset(self):
        dev = self.dev
        if dev is None:
            raise ValueError(f"{self} not found")
        dev.reset()
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
        logger = LoggerConfig.setup_service_logger()
        logger.info(f"Starting run loop for DisplayDevice(vid={hex(self.vid)}, pid={hex(self.pid)})")
        try:
            while True:
                # Simulate communication with the device
                logger.debug("Attempting to communicate with the device...")
                if not self.is_device_connected():
                    logger.warning(f"Device(vid={hex(self.vid)}, pid={hex(self.pid)}) not found, retrying...")
                    time.sleep(1)  # Retry delay
                    continue

                # Example: Send a test command to the device
                try:
                    self.send_test_command()
                    logger.debug("Test command sent successfully")
                except Exception as e:
                    logger.error(f"Failed to send test command: {e}")
                    raise

                # Example: Receive a response from the device
                try:
                    response = self.receive_response()
                    logger.debug(f"Received response: {response}")
                except Exception as e:
                    logger.error(f"Failed to receive response: {e}")
                    raise

                time.sleep(1)  # Main loop delay
        except Exception as e:
            logger.error(f"Run loop encountered an error: {e}")
            raise

    def is_device_connected(self):
        self.logger.debug(f"Checking connection for Device(vid={hex(self.vid)}, pid={hex(self.pid)})")
        try:
            device = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            if device:
                self.logger.debug(f"Device(vid={hex(self.vid)}, pid={hex(self.pid)}) is connected")
                return True
            else:
                self.logger.debug(f"Device(vid={hex(self.vid)}, pid={hex(self.pid)}) is not connected")
                return False
        except Exception as e:
            self.logger.error(f"Error while checking device connection: {e}")
            return False

    def send_test_command(self):
        # Placeholder for sending a command to the device
        pass

    def receive_response(self):
        # Placeholder for receiving a response from the device
        return "OK"


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
        super().__init__(0x0402, 0x3992, 512, 320, 240, config_dir)

    def get_header(self) -> bytes:
        prefix = bytes([0xDA, 0xDB, 0xDC, 0xDD])
        body = struct.pack('<6HIH', 2, 1, 320, 240, 2, 0, 153600, 0)
        return prefix + body

    def run(self):
        self.logger.info(f"{self} running")
        time.sleep(1)  # Give USB stack time to settle

        for attempt in range(10):
            self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            if self.dev is not None:
                break
            self.logger.warning(f"{self} not found (attempt {attempt + 1}), retrying...")
            time.sleep(0.5)

        if self.dev is None:
            self.logger.error(f"{self} not found during run() after retries")
            return

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


DEVICE_CLASSES = {
    (0x0418, 0x5303): DisplayDevice04185303,
    (0x0418, 0x5304): DisplayDevice04185304,
    (0x0416, 0x8001): DisplayDevice04168001,
    (0x0416, 0x5302): DisplayDevice04165302,
    (0x0402, 0x3922): DisplayDevice04023922,
}


