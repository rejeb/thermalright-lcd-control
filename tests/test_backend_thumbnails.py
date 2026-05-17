# SPDX-License-Identifier: Apache-2.0
"""Thumbnail generation helpers moved to gui/components/thumbnail_render.py
(the pure render module shared by the GUI and the background worker). These
tests pin the behaviors that used to live as ThumbnailMixin helpers."""
import pyvips


def _png_dims(png: bytes):
    img = pyvips.Image.new_from_buffer(png, "")
    return img.width, img.height


def test_png_data_url_roundtrip():
    from thermalright_lcd_control.gui.components import thumbnail_render as tr
    url = tr.data_url(b"payload")
    assert url.startswith("data:image/png;base64,")


def test_contain_fits_in_thumb_box():
    from thermalright_lcd_control.device_controller.display import vips_utils as vu
    from thermalright_lcd_control.gui.components import thumbnail_render as tr
    out = tr._contain(vu.to_rgba(vu.solid(200, 50, (0, 0, 0, 255))),
                      tr.THUMB_W, tr.THUMB_H)
    assert (out.width, out.height) == (160, 120)


def test_cover_thumbnail_from_image(tmp_path):
    from thermalright_lcd_control.device_controller.display import vips_utils as vu
    from thermalright_lcd_control.gui.components import thumbnail_render as tr
    p = tmp_path / "wide.png"
    vu.to_rgb(vu.solid(200, 50, (0, 128, 255, 255))).write_to_file(str(p))
    png = tr.render_image(str(p), tr.THUMB_W, tr.THUMB_H, keep_alpha=False)
    assert _png_dims(png) == (160, 120)
