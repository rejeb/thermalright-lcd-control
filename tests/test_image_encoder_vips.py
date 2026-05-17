# SPDX-License-Identifier: Apache-2.0
from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.image_encoder import (
    ImageEncoder,
    encode_jpeg,
    encode_rgb565_be,
    encode_rgb565_le_columns,
)


def _img(w, h, rgb):
    return vu.to_rgb(vu.solid(w, h, (*rgb, 255)))


def test_rgb565_be_pure_red():
    data = encode_rgb565_be(_img(2, 2, (255, 0, 0)), 2, 2)
    assert data == bytes([0xF8, 0x00]) * 4          # 0b11111_000000_00000 BE


def test_rgb565_le_columns_layout():
    # 2x2, all white; column-major LE with last pixel of each column zeroed
    data = encode_rgb565_le_columns(_img(2, 2, (255, 255, 255)), 2, 2)
    assert len(data) == 8
    assert data[0:2] == b"\xff\xff"                  # 0xFFFF LE
    assert data[2:4] == b"\x00\x00"                  # column end zeroed


def test_encode_resizes_to_target():
    data = encode_rgb565_be(_img(4, 4, (0, 0, 255)), 2, 2)
    assert len(data) == 2 * 2 * 2


def test_jpeg_magic_and_factory():
    img = _img(8, 8, (10, 200, 30))
    assert encode_jpeg(img, 8, 8)[:2] == b"\xff\xd8"
    assert ImageEncoder.encode(img, "jpeg", 8, 8)[:2] == b"\xff\xd8"
