import numpy as np
from PIL import Image
from .display_device import DisplayDevice

class FrozenWarframeLCD(DisplayDevice):
    def __init__(self, config_dir: str):
        super().__init__(0x0402, 0x3922, 512, 320, 240, config_dir)

    def get_header(self) -> bytes:
        payload_length = self.width * self.height * 2  # RGB565 = 2 bytes per pixel
        return b'\xAB\xCD' + payload_length.to_bytes(2, 'little')

    # Optional: override _encode_image if your device needs a different format
    # Otherwise, use the inherited version from DisplayDevice
