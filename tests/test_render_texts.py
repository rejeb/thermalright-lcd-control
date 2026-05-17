# SPDX-License-Identifier: Apache-2.0
"""The device renders standalone text overlays; metrics render the value only."""
from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import MetricConfig, TextConfig
from thermalright_lcd_control.device_controller.display.text_renderer import TextRenderer


def _ink(img):
    return int(vu.to_numpy(img)[:, :, 3].max())


def test_render_texts_draws_ink():
    tr = TextRenderer()
    overlay = vu.solid(160, 80, (0, 0, 0, 0))
    out = tr.render_texts(overlay, [TextConfig(
        text="CPU", position=(10, 10), font_size=24, color=(255, 255, 255, 255))])
    assert _ink(out) > 0


def test_render_texts_skips_empty_and_disabled():
    tr = TextRenderer()
    overlay = vu.solid(160, 80, (0, 0, 0, 0))
    out = tr.render_texts(overlay, [
        TextConfig(text="", position=(10, 10), font_size=24, color=(255, 255, 255, 255)),
        TextConfig(text="x", position=(10, 10), font_size=24,
                   color=(255, 255, 255, 255), enabled=False)])
    assert _ink(out) == 0


def test_render_metrics_does_not_draw_label():
    # A metric that still carries a label must NOT render it (value-only).
    tr = TextRenderer()
    overlay = vu.solid(200, 80, (0, 0, 0, 0))
    m = MetricConfig(name="cpu_temperature", position=(0, 0), font_size=20,
                     color=(255, 255, 255, 255), unit="C", precision=0,
                     label="CPU", label_position=(120, 40), label_font_size=40)
    out = tr.render_metrics(overlay, {"cpu_temperature": 46}, [m])
    # only the value (top-left) drew ink; the label region (right side) is blank
    right = vu.to_numpy(out)[:, 120:, 3]
    assert int(right.max()) == 0
