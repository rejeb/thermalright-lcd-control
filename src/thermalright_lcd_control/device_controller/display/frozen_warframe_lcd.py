import numpy as np
from PIL import Image
from .display_device import DisplayDevice

class FrozenWarframeLCD(DisplayDevice):
    def get_header(self, image_data: bytes) -> bytes:
        # This header may vary — adjust based on your USB capture
        # Example: 2-byte magic + 2-byte length
        return b'\xAB\xCD' + len(image_data).to_bytes(2, 'little')

    def _encode_image(self, image: Image.Image) -> bytes:
        # Resize to native resolution
        image = image.resize((320, 240)).convert('RGB')
        arr = np.array(image)

        # Convert RGB888 to RGB565
        r = (arr[..., 0] >> 3).astype(np.uint16)
        g = (arr[..., 1] >> 2).astype(np.uint16)
        b = (arr[..., 2] >> 3).astype(np.uint16)
        rgb565 = (r << 11) | (g << 5) | b

        # Flatten and convert to bytes
        return rgb565.flatten().tobytes()
