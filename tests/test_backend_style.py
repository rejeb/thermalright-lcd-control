import unittest

from thermalright_lcd_control.gui.backend.app_backend import (
    OverlayWidgetsAdapter,
    TextStyle,
)


class TestAdapterStyle(unittest.TestCase):
    def _adapter(self, widgets):
        return OverlayWidgetsAdapter(widgets, TextStyle(), 320, 240)

    def test_metric_has_no_label_and_text_keeps_own_style(self):
        widgets = [
            {"id": 1, "type": "metric", "key": "cpu_temperature",
             "fx": 0.3, "fy": 0.4, "font_size": 24, "color": "#FFFFFF",
             "font_family": "DejaVu Sans", "bold": True, "italic": False,
             "unit": "C", "prec": 0},
            {"id": 2, "type": "text", "text": "CPU",
             "fx": 0.3, "fy": 0.2, "font_size": 18, "color": "#00FF00",
             "font_family": "Noto Sans", "bold": False, "italic": True},
        ]
        cfg = self._adapter(widgets).to_display_config()
        m = cfg["metrics"]["configs"][0]
        self.assertEqual(m["font_family"], "DejaVu Sans")
        self.assertNotIn("label", m)             # metrics carry no label anymore
        self.assertNotIn("label_font_size", m)
        # the label is an independent text overlay with its OWN style/size
        texts = cfg["texts"]
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0]["text"], "CPU")
        self.assertEqual(texts[0]["font_size"], 18)
        self.assertEqual(texts[0]["font_family"], "Noto Sans")
        self.assertFalse(texts[0]["bold"])
        self.assertTrue(texts[0]["italic"])

    def test_hidden_text_not_emitted(self):
        widgets = [
            {"id": 1, "type": "metric", "key": "cpu_temperature", "fx": 0.5,
             "fy": 0.5, "font_size": 20, "color": "#FFFFFF", "unit": "C", "prec": 0},
            {"id": 2, "type": "text", "text": "CPU", "fx": 0.3, "fy": 0.5,
             "font_size": 18, "color": "#FFFFFF", "hidden": True},
        ]
        cfg = self._adapter(widgets).to_display_config()
        self.assertEqual(cfg["texts"], [])

    def test_blank_text_not_emitted(self):
        widgets = [{"id": 2, "type": "text", "text": "   ", "fx": 0.3, "fy": 0.5,
                    "font_size": 18, "color": "#FFFFFF"}]
        cfg = self._adapter(widgets).to_display_config()
        self.assertEqual(cfg["texts"], [])

    def test_clock_style_emitted(self):
        widgets = [{"id": 3, "type": "clock", "mode": "time", "fx": 0.5, "fy": 0.5,
                    "font_size": 22, "color": "#FFFFFF",
                    "font_family": "Ubuntu", "bold": True, "italic": False}]
        cfg = self._adapter(widgets).to_display_config()
        self.assertEqual(cfg["time"]["font_family"], "Ubuntu")
        self.assertTrue(cfg["time"]["bold"])
        self.assertFalse(cfg["time"]["italic"])


if __name__ == "__main__":
    unittest.main()
