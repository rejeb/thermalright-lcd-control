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


class DisplayDevice04165302(HidDevice):
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
