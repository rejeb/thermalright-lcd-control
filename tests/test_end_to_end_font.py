import unittest

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import (
    BackgroundType,
    DisplayConfig,
    MetricConfig,
)
from thermalright_lcd_control.device_controller.display.text_renderer import TextRenderer


class TestEndToEndFont(unittest.TestCase):
    def test_styled_metric_renders_without_error_and_differs(self):
        DisplayConfig(background_path="", background_type=BackgroundType.IMAGE)
        tr = TextRenderer()

        def render(metric):
            overlay = vu.solid(320, 240, (0, 0, 0, 0))
            out = tr.render_metrics(overlay, {"cpu_temperature": 46}, [metric])
            return vu.to_numpy(out).tobytes()

        plain = MetricConfig(name="cpu_temperature", position=(20, 20), font_size=40,
                             format_string="{label}{value}{unit}", unit="C", precision=0)
        bold = MetricConfig(name="cpu_temperature", position=(20, 20), font_size=40,
                            font_family="DejaVu Sans", bold=True,
                            format_string="{label}{value}{unit}", unit="C", precision=0)
        # Bold should paint more/different pixels than the default face.
        self.assertNotEqual(render(plain), render(bold))


if __name__ == "__main__":
    unittest.main()
