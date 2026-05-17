# SPDX-License-Identifier: Apache-2.0
from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.text_renderer import TextRenderer


def _blank(w=120, h=60):
    return vu.solid(w, h, (0, 0, 0, 0))


def test_draw_text_paints_pixels_at_position():
    tr = TextRenderer()
    out = tr._draw_text(_blank(), (10, 5), "88", "#FF0000FF", 20, None, False, False)
    arr = vu.to_numpy(out)
    assert (out.width, out.height) == (120, 60)
    region = arr[5:35, 10:60]
    assert region[..., 3].max() > 0                 # something was drawn
    assert arr[..., 3][:5, :].max() == 0            # nothing above position.y
    assert arr[..., 3][:, :10].max() == 0           # nothing left of position.x


def test_draw_text_color():
    tr = TextRenderer()
    out = tr._draw_text(_blank(), (0, 0), "88", (0, 255, 0), 24, None, False, False)
    arr = vu.to_numpy(out)
    ys, xs = (arr[..., 3] > 200).nonzero()
    assert len(xs) > 0
    px = arr[ys[0], xs[0]]
    assert px[1] > 200 and px[0] < 50 and px[2] < 50


def test_draw_text_clips_offcanvas():
    tr = TextRenderer()
    out = tr._draw_text(_blank(20, 10), (15, 5), "8888888", "#FFFFFF", 30, None, False, False)
    assert (out.width, out.height) == (20, 10)      # no canvas growth
