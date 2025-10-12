import struct
from abc import ABC

import hid

from .display_device import DisplayDevice


class HidDevice(DisplayDevice, ABC):

    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, *args, **kwargs):
        super().__init__(vid, pid, chunk_size, width, height, config_dir, *args, **kwargs)
        self.dev = hid.Device(vid, pid)
        self.vid = vid
        self.pid = pid
        self.chunk_size = chunk_size
        self.height = height
        self.width = width
        self.header = self.get_header()
        self.config_dir = config_dir

    def send_packet(self, packet: bytes):
        """Send packet to device"""
        self.dev.write(packet)


class DisplayDevice04185304(HidDevice):
    W, H = 480, 480
    VID, PID = 0x0418, 0x5304

    def __init__(self, config_dir: str):
        super().__init__(self.VID, self.PID, 512, self.W, self.H, config_dir)

    def get_header(self) -> bytes:
        return struct.pack('<BBHHH',
                           0x69,
                           0x88,
                           480,
                           480,
                           0
                           )

    @staticmethod
    def info() -> dict:
        return {
            "class_name": f"{DisplayDevice04185304.__module__}.{DisplayDevice04185304.__name__}",
            "width": DisplayDevice04185304.W,
            "height": DisplayDevice04185304.H,
            "vid": DisplayDevice04185304.VID,
            "pid": DisplayDevice04185304.PID,
        }


class DisplayDevice04165302(HidDevice):
    W, H = 320, 240
    VID, PID = 0x0416, 0x5302

    def __init__(self, config_dir: str):
        super().__init__(self.VID, self.PID, 512, self.W, self.H, config_dir)

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

    @staticmethod
    def info() -> dict:
        return {
            "class_name": f"{DisplayDevice04165302.__module__}.{DisplayDevice04165302.__name__}",
            "width": DisplayDevice04165302.W,
            "height": DisplayDevice04165302.H,
            "vid": DisplayDevice04165302.VID,
            "pid": DisplayDevice04165302.PID,
        }
