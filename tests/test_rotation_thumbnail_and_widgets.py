# SPDX-License-Identifier: Apache-2.0
"""After a rotation, a theme's thumbnail and its widget positions must use the
swapped ``<h><w>`` resolution:

* ``_background_of`` (theme thumbnail) resolves ``{resolution}`` at the current
  rotation, else a rotated theme shows its un-rotated background thumbnail.
* ``_widgets_from_config`` normalizes pixel positions against the config's
  rotation-swapped output dims, else every widget is misplaced after rotation.
"""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.device_controller.display import vips_utils as vu  # noqa: E402

_ACTIVE = """\
display:
  rotation: 0
  background: {{path: "{d}/{{resolution}}/a001.png", type: image}}
  foreground: {{enabled: false, path: "", position: {{x: 0, y: 0}}, alpha: 1.0}}
  metrics: {{enabled: false, configs: []}}
  date: {{enabled: false}}
  time: {{enabled: false}}
  texts: []
"""
_PRESET = """\
display:
  rotation: 0
  background: {{path: "{d}/{{resolution}}/a001.png", type: image}}
  foreground: {{enabled: false, path: "", position: {{x: 0, y: 0}}, alpha: 1.0}}
  metrics:
    enabled: true
    configs:
    - {{name: cpu_temperature, enabled: true, position: {{x: 120, y: 160}},
       font_size: 18, color: "#FFFFFFFF", unit: "C", precision: 0,
       format_string: "{{value}}{{unit}}"}}
  date: {{enabled: false}}
  time: {{enabled: false}}
  texts: []
"""


def _app():
    return QApplication.instance() or QApplication([])


class TestRotationThumbnailAndWidgets(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        Path(d, "config_dev1.yaml").write_text(_ACTIVE.format(d=d))
        pr = Path(d, "presets")
        for res, (w, h) in (("320240", (320, 240)), ("240320", (240, 320))):
            (pr / res).mkdir(parents=True)
            Path(d, res).mkdir()
            vu.to_rgb(vu.solid(w, h, (1, 2, 3, 255))).write_to_file(str(Path(d, res, "a001.png")))
        (pr / "240320" / "config_1.yaml").write_text(_PRESET.format(d=d))
        cfg = {"paths": {"service_config": d, "themes_dir": str(pr), "backgrounds_dir": d},
               "supported_formats": {"images": [".png"]}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=None)

    def test_thumbnail_follows_rotation(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            preset = Path(d, "presets", "240320", "config_1.yaml")
            self.assertIn("320240", be._background_of(preset))
            be.set_rotation(90)
            self.assertIn("240320", be._background_of(preset))

    def test_widget_positions_normalized_to_rotated_resolution(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.set_rotation(90)
            be.select_theme(str(Path(d, "presets", "240320", "config_1.yaml")))
            metric = next(w for w in json.loads(be.get_widgets())
                          if w["type"] == "metric")
            # position (120,160) in 240x320 space → ~0.50, ~0.50 (not /320, /240)
            self.assertAlmostEqual(metric["fx"], 120 / 240, delta=0.05)
            self.assertAlmostEqual(metric["fy"], 160 / 320, delta=0.05)


if __name__ == "__main__":
    unittest.main()
