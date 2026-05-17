# SPDX-License-Identifier: Apache-2.0
"""Rotating keeps the selected theme and loads its per-orientation variant.

The same theme name exists in both the ``<w><h>`` and ``<h><w>`` preset folders
(imported per-orientation themes). Rotating must re-select that theme for the new
orientation so its metric positions match — not fall back to the single-
orientation active config (which would leave metrics at the old positions).
"""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.device_controller.display import vips_utils as vu  # noqa: E402

_HEAD = """\
display:
  rotation: 0
  background: {{path: "{d}/{{resolution}}/a001.png", type: image}}
  foreground: {{enabled: false, path: "", position: {{x: 0, y: 0}}, alpha: 1.0}}
"""
_METRIC = """\
  metrics:
    enabled: true
    configs:
    - {{name: cpu_temperature, enabled: true, position: {{x: {x}, y: {y}}},
       font_size: 18, color: "#FFFFFFFF", unit: "C", precision: 0,
       format_string: "{{value}}{{unit}}"}}
  date: {{enabled: false}}
  time: {{enabled: false}}
  texts: []
"""


def _cfg(d, x, y):
    return _HEAD.format(d=d) + _METRIC.format(x=x, y=y)


def _app():
    return QApplication.instance() or QApplication([])


class TestRotationKeepsTheme(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        Path(d, "config_dev1.yaml").write_text(_cfg(d, 10, 10))
        pr = Path(d, "presets")
        for res, (w, h), (x, y) in (("320240", (320, 240), (288, 120)),
                                    ("240320", (240, 320), (48, 288))):
            (pr / res).mkdir(parents=True)
            Path(d, res).mkdir()
            vu.to_rgb(vu.solid(w, h, (1, 2, 3, 255))).write_to_file(str(Path(d, res, "a001.png")))
            (pr / res / "config_1.yaml").write_text(_cfg(d, x, y))
        cfg = {"paths": {"service_config": d, "themes_dir": str(pr), "backgrounds_dir": d},
               "supported_formats": {"images": [".png"]}}
        be = AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                               "width": 320, "height": 240}], event_bus=None)

        # mirror main_window.reload_for_device sticky selection
        def _reload():
            cur = be.current_theme_name
            themes = json.loads(be.get_themes())
            if themes:
                target = next((t for t in themes if t.get("name") == cur), themes[0])
                be.select_theme(target["yaml_path"])
        be.device_changed.connect(_reload)
        return be

    def _metric(self, be):
        return next(w for w in json.loads(be.get_widgets()) if w["type"] == "metric")

    def test_rotation_loads_same_theme_new_orientation_positions(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.select_theme(str(Path(d, "presets", "320240", "config_1.yaml")))
            m = self._metric(be)
            self.assertAlmostEqual(m["fx"], 288 / 320, delta=0.03)
            self.assertAlmostEqual(m["fy"], 120 / 240, delta=0.03)

            be.set_rotation(90)

            self.assertEqual(be.current_rotation, 90)
            self.assertEqual(be.current_theme_name, "Config 1")
            m = self._metric(be)          # 240320 preset's own position
            self.assertAlmostEqual(m["fx"], 48 / 240, delta=0.03)
            self.assertAlmostEqual(m["fy"], 288 / 320, delta=0.03)


if __name__ == "__main__":
    unittest.main()
