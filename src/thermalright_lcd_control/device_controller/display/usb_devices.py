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
        # TODO implement logic for usb devices
        self.dev.write(packet)
