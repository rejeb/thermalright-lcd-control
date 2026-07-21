# SPDX-License-Identifier: Apache-2.0
import base64

import pytest
import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.gui.components import thumbnail_render as tr


def _png_dims(png: bytes):
    img = pyvips.Image.new_from_buffer(png, "")
    return img.width, img.height


def test_render_image_cover_returns_png_at_thumb_size(tmp_path):
    src = tmp_path / "bg.png"
    vu.to_rgb(vu.solid(400, 300, (10, 20, 30, 255))).write_to_file(str(src))
    png = tr.render_image(str(src), tr.THUMB_W, tr.THUMB_H, keep_alpha=False)
    assert _png_dims(png) == (tr.THUMB_W, tr.THUMB_H)


def test_render_image_keep_alpha_fits_within_box(tmp_path):
    src = tmp_path / "fg.png"
    vu.to_rgba(vu.solid(600, 100, (0, 0, 0, 128))).write_to_file(str(src))
    png = tr.render_image(str(src), tr.THUMB_W, tr.THUMB_H, keep_alpha=True)
    assert _png_dims(png) == (tr.THUMB_W, tr.THUMB_H)


def test_gradient_returns_png_at_thumb_size():
    png = tr.gradient(206, tr.THUMB_W, tr.THUMB_H)
    assert _png_dims(png) == (tr.THUMB_W, tr.THUMB_H)


def test_data_url_roundtrips():
    url = tr.data_url(b"hello")
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == b"hello"


def test_render_video_first_frame(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    p = tmp_path / "clip.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24))
    for i in range(4):
        w.write(np.full((24, 32, 3), i * 30, dtype=np.uint8))
    w.release()
    png = tr.render_video(str(p), tr.THUMB_W, tr.THUMB_H)
    assert _png_dims(png) == (tr.THUMB_W, tr.THUMB_H)
