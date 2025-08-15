from abc import ABC

from PIL import Image

from .display_device import DisplayDevice
import usb.core

class UsbDevice(DisplayDevice, ABC):
    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, *args, **kwargs):
        super().__init__(vid, pid, chunk_size, width, height, config_dir, *args, **kwargs)
        self.dev = usb.core.find(idVendor=vid, idProduct=pid)  # init usb device
        self.vid = vid
        self.pid = pid
        self.chunk_size = chunk_size
        self.width = width
        self.height = height
        self.config_dir = config_dir

    def _encode_image(self, img: Image) -> bytearray:
        # if image encoding logic is different then implement logic here or at DisplayDevice04023922 level
        # You can let this at the end, if encoding is not good, the screen will display a blurry image.
        return super()._encode_image(img)

    def send_packet(self, packet: bytes):
        """Send packet to device"""
        # Implement your own logic here to send packet to device
        self.dev.write(packet)


class DisplayDevice04023922(UsbDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0402, 0x3922, 512, 320, 240, config_dir)
        # change report_id value if different from bytes([0x00]), this byte is appended to every packet.
        # self.report_id = "new value"

    def get_header(self) -> bytes:
        # Implement your own logic here to get header bytes
        return bytes([0x00, 0x00, 0x00, 0x00])
