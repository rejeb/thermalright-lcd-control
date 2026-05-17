# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest

from thermalright_lcd_control.device_controller.display import vips_utils as vu


def test_solid_and_to_numpy():
    img = vu.solid(4, 3, (10, 20, 30, 255))
    assert (img.width, img.height, img.bands) == (4, 3, 4)
    arr = vu.to_numpy(img)
    assert arr.shape == (3, 4, 4)
    assert tuple(arr[0, 0]) == (10, 20, 30, 255)


def test_numpy_roundtrip():
    arr = np.arange(2 * 3 * 3, dtype=np.uint8).reshape(2, 3, 3)
    out = vu.to_numpy(vu.from_numpy(arr))
    assert np.array_equal(out, arr)


def test_to_rgb_flattens_alpha():
    img = vu.solid(2, 2, (255, 0, 0, 0))       # fully transparent red
    rgb = vu.to_rgb(img)
    assert rgb.bands == 3
    assert tuple(vu.to_numpy(rgb)[0, 0]) == (0, 0, 0)   # flattened over black


def test_jpeg_roundtrip():
    img = vu.to_rgb(vu.solid(8, 8, (200, 100, 50, 255)))
    data = vu.jpeg_bytes(img, quality=85)
    assert data[:2] == b"\xff\xd8"
    back = vu.from_jpeg(data)
    assert (back.width, back.height) == (8, 8)


def test_resize_to_exact_size():
    img = vu.solid(10, 6, (1, 2, 3, 255))
    out = vu.resize_to(img, 5, 12)
    assert (out.width, out.height) == (5, 12)


def test_overlay_at_composites_alpha():
    base = vu.solid(4, 4, (0, 0, 255, 255))
    over = vu.solid(2, 2, (255, 0, 0, 255))
    out = vu.overlay_at(base, over, 1, 1)
    arr = vu.to_numpy(out)
    assert tuple(arr[1, 1][:3]) == (255, 0, 0)
    assert tuple(arr[0, 0][:3]) == (0, 0, 255)


@pytest.mark.parametrize("deg,expect", [(0, (3, 2)), (90, (2, 3)), (180, (3, 2)), (270, (2, 3))])
def test_rotate_dimensions(deg, expect):
    img = vu.solid(3, 2, (9, 9, 9, 255))
    out = vu.rotate(img, deg)
    assert (out.width, out.height) == expect


def test_rotate_90_is_clockwise():
    # 2x1 image: left pixel red, right pixel green. Clockwise 90 → red on top.
    arr = np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8)
    out = vu.to_numpy(vu.rotate(vu.from_numpy(arr), 90))
    assert tuple(out[0, 0]) == (255, 0, 0)
    assert tuple(out[1, 0]) == (0, 255, 0)
