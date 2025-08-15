import numpy as np
from PIL import Image
from .display_device import DisplayDevice

class FrozenWarframeLCD(DisplayDevice):
    """
    Driver for the Thermalright Frozen Warframe LCD.
    Handles USB header generation and inherits image encoding from DisplayDevice.
    """

    def __init__(self, config_dir: str):
        # VID:PID = 0402:3922, resolution = 320x240
        super().__init__(0x0402, 0x3922, 512, 320, 240, config_dir)

        # Sanity check to ensure resolution matches expectations
        assert self.width == 320 and self.height == 240, "Unexpected resolution for Frozen Warframe LCD"

    def get_header(self) -> bytes:
        """
        Constructs the USB packet header for the Frozen Warframe LCD.
        Format: [0xAB, 0xCD, payload_length_low, payload_length_high]
        Payload length is calculated as width * height * 2 (RGB565 encoding).
        """
        return self._build_header(self.width, self.height)

    def _build_header(self, width: int, height: int) -> bytes:
        """
        Helper method to build the header. Can be overridden by subclasses if needed.
        """
        payload_length = width * height * 2  # RGB565 = 2 bytes per pixel
        return b'\xAB\xCD' + payload_length.to_bytes(2, 'little')

    # Optional: override _encode_image if your device needs a different format
    
