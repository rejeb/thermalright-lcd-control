import unittest

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import (
    BackgroundType,
    DisplayConfig,
    MetricConfig,
    TextConfig,
)
from thermalright_lcd_control.device_controller.display.font_manager import ResolvedFont
from thermalright_lcd_control.device_controller.display.text_renderer import TextRenderer


class FakeFontManager:
    def __init__(self):
        self.calls = []

    def get_font(self, size, family=None, bold=False, italic=False):
        self.calls.append((size, family, bold, italic))
        return ResolvedFont(path=None, family=family or "sans", size=size)


def _renderer():
    DisplayConfig(background_path="", background_type=BackgroundType.IMAGE)
    tr = TextRenderer()
    tr.font_manager = FakeFontManager()
    return tr


def _overlay():
    return vu.solid(240, 200, (0, 0, 0, 0))


class TestRendererFont(unittest.TestCase):
    def test_metric_value_uses_own_style(self):
        tr = _renderer()
        m = MetricConfig(
            name="cpu_temperature", position=(100, 100), font_size=24,
            font_family="DejaVu Sans", bold=True, italic=False,
            format_string="{value}{unit}", unit="C", precision=0)
        tr.render_metrics(_overlay(), {"cpu_temperature": 46}, [m])
        self.assertIn((24, "DejaVu Sans", True, False), tr.font_manager.calls)

    def test_text_uses_own_style(self):
        # A label is an independent text overlay with its own (smaller) size.
        tr = _renderer()
        t = TextConfig(text="CPU", position=(160, 140), font_size=18,
                       font_family="Noto Sans", bold=False, italic=True)
        tr.render_texts(_overlay(), [t])
        self.assertIn((18, "Noto Sans", False, True), tr.font_manager.calls)

    def test_date_uses_textconfig_style(self):
        tr = _renderer()
        cfg = TextConfig(font_size=20, font_family="Ubuntu", bold=False, italic=True,
                         position=(0, 0), enabled=True)
        tr.render_date(_overlay(), cfg)
        self.assertIn((20, "Ubuntu", False, True), tr.font_manager.calls)


if __name__ == "__main__":
    unittest.main()
