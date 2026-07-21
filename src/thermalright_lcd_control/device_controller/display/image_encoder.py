# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Image encoding factory: convert a pyvips image to device-specific byte formats."""
from collections.abc import Callable
from enum import Enum

import numpy as np
import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu


class ImageEncoding(str, Enum):
    """Supported device payload encodings, selectable by name."""
    RGB565_LE_COLUMNS = "rgb565_le_columns"  # column-major, vertical flip, last pixel/column zeroed
    RGB565_BE = "rgb565_be"                  # row-major big-endian
    JPEG = "jpeg"


def _fit_rgb(img: pyvips.Image, width: int, height: int) -> pyvips.Image:
    if (img.width, img.height) != (width, height):
        img = vu.resize_to(img, width, height)
    return vu.to_rgb(img)


def encode_rgb565_le_columns(img: pyvips.Image, width: int, height: int, **_) -> bytes:
    """RGB565 little-endian, column-major after vertical flip; last pixel of each column = 0."""
    arr = vu.to_numpy(_fit_rgb(img, width, height))             # (H, W, 3)
    arr_t = np.ascontiguousarray(arr[::-1].transpose(1, 0, 2))  # (W, H, 3)
    out = (arr_t[..., 0].astype(np.uint16) & 0xF8) << 8
    out |= (arr_t[..., 1].astype(np.uint16) & 0xFC) << 3
    out |= arr_t[..., 2].astype(np.uint16) >> 3
    out[:, -1] = 0
    return out.astype('<u2').tobytes()


def encode_rgb565_be(img: pyvips.Image, width: int, height: int, **_) -> bytes:
    """RGB565 big-endian, row-major (no rotation/flip)."""
    arr = vu.to_numpy(_fit_rgb(img, width, height))
    r = arr[..., 0].astype(np.uint16)
    g = arr[..., 1].astype(np.uint16)
    b = arr[..., 2].astype(np.uint16)
    v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    out = np.empty((height, width * 2), dtype=np.uint8)
    out[..., 0::2] = (v >> 8).astype(np.uint8)
    out[..., 1::2] = (v & 0xFF).astype(np.uint8)
    return out.tobytes()


def encode_jpeg(img: pyvips.Image, width: int, height: int, jpeg_quality: int = 85, **_) -> bytes:
    """JPEG-compressed payload."""
    return vu.jpeg_bytes(_fit_rgb(img, width, height), quality=jpeg_quality)


_ENCODERS: dict[ImageEncoding, Callable[..., bytes]] = {
    ImageEncoding.RGB565_LE_COLUMNS: encode_rgb565_le_columns,
    ImageEncoding.RGB565_BE: encode_rgb565_be,
    ImageEncoding.JPEG: encode_jpeg,
}


class ImageEncoder:
    """Factory: encode a pyvips image to bytes for a named encoding."""

    @staticmethod
    def encode(img: pyvips.Image, encoding: ImageEncoding | str, width: int, height: int,
               **kwargs) -> bytes:
        encoding = ImageEncoding(encoding)
        return _ENCODERS[encoding](img, width, height, **kwargs)
