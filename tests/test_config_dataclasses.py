import unittest

from thermalright_lcd_control.device_controller.display.config import MetricConfig, TextConfig


class TestConfigStyleDefaults(unittest.TestCase):
    def test_textconfig_style_defaults(self):
        t = TextConfig()
        self.assertIsNone(t.font_family)
        self.assertFalse(t.bold)
        self.assertFalse(t.italic)

    def test_metricconfig_value_style_defaults(self):
        m = MetricConfig(name="cpu_temperature")
        self.assertIsNone(m.font_family)
        self.assertFalse(m.bold)
        self.assertFalse(m.italic)

    def test_metricconfig_label_style_defaults(self):
        m = MetricConfig(name="cpu_temperature")
        self.assertIsNone(m.label_font_family)
        self.assertFalse(m.label_bold)
        self.assertFalse(m.label_italic)


if __name__ == "__main__":
    unittest.main()
