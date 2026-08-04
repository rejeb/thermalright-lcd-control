# SPDX-License-Identifier: Apache-2.0
"""The Clock widget is split into Date / Time / Day-of-week: a weekday clock
widget maps to a ``weekday`` config section, loads back as a weekday widget, and
renders the weekday name. Old configs without a ``weekday`` key still load."""
import os
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.device_controller.display import vips_utils as vu  # noqa: E402
from thermalright_lcd_control.device_controller.display.config_loader import (
    ConfigLoader,  # noqa: E402
)
from thermalright_lcd_control.device_controller.display.text_renderer import (
    TextRenderer,  # noqa: E402
)


def _app():
    return QApplication.instance() or QApplication([])


def _disp(weekday_enabled: bool, include_weekday_key: bool = True) -> dict:
    d = {
        "rotation": 0,
        "background": {"path": "", "type": "image"},
        "foreground": {"enabled": False, "path": "", "position": {"x": 0, "y": 0}, "alpha": 1.0},
        "metrics": {"enabled": False, "configs": []},
        "date": {"enabled": False},
        "time": {"enabled": False},
        "texts": [],
    }
    if include_weekday_key:
        d["weekday"] = {"enabled": weekday_enabled, "text": "",
                        "position": {"x": 10, "y": 20}, "font_size": 22,
                        "color": "#FFFFFFFF", "font_family": None,
                        "bold": False, "italic": False}
    return {"display": d}


class TestWeekdayWidget(unittest.TestCase):
    def setUp(self):
        _app()

    def test_weekday_section_loads_into_config(self):
        cfg = ConfigLoader().load_config_from_dict(_disp(True), 320, 240)
        self.assertIsNotNone(cfg.weekday_config)
        self.assertEqual(cfg.weekday_config.position, (10, 20))

    def test_missing_weekday_key_is_backward_compatible(self):
        cfg = ConfigLoader().load_config_from_dict(
            _disp(False, include_weekday_key=False), 320, 240)
        self.assertIsNone(cfg.weekday_config)

    def test_render_weekday_draws_day_name(self):
        cfg = ConfigLoader().load_config_from_dict(_disp(True), 320, 240)
        overlay = vu.solid(320, 240, (0, 0, 0, 0))
        out = TextRenderer().render_weekday(overlay, cfg.weekday_config,
                                            datetime(2026, 7, 20))  # a Monday
        self.assertIsNot(out, overlay)     # something was drawn

    def test_adapter_maps_weekday_clock_widget(self):
        from thermalright_lcd_control.gui.backend.app_backend import (
            OverlayWidgetsAdapter,
            TextStyle,
        )
        widgets = [{"id": 1, "type": "clock", "mode": "weekday", "fx": 0.1, "fy": 0.2,
                    "font_size": 22, "color": "#FFFFFFFF", "font_family": None,
                    "bold": False, "italic": False}]
        dc = OverlayWidgetsAdapter(widgets, TextStyle(), 320, 240).to_display_config()
        self.assertTrue(dc["weekday"]["enabled"])
        self.assertFalse(dc["date"]["enabled"])
        self.assertFalse(dc["time"]["enabled"])


if __name__ == "__main__":
    unittest.main()
