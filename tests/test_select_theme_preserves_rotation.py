# SPDX-License-Identifier: Apache-2.0
"""Regression: selecting a PRESET theme must not reset the device rotation.

A preset's config stores rotation 0; before the fix, select_theme adopted that
and snapped the device back to 0°, flipping the media resolution to the
un-rotated folder (so a rotated-grid preset loaded the wrong-orientation media).
The device's own active config still restores its saved rotation on load.
"""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

_PRESET = """\
display:
  rotation: 0
  background: {{path: "{d}/{{resolution}}/a001.png", type: image}}
  foreground: {{enabled: false, path: "", position: {{x: 0, y: 0}}, alpha: 1.0}}
  metrics: {{enabled: false, configs: []}}
  date: {{enabled: false}}
  time: {{enabled: false}}
  texts: []
"""


def _app():
    return QApplication.instance() or QApplication([])


class TestSelectThemePreservesRotation(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        # active config for the device + a preset under presets/<res>/
        (Path(d) / "config_dev1.yaml").write_text(_PRESET.format(d=d))
        presets = Path(d) / "presets" / "240320"
        presets.mkdir(parents=True)
        (presets / "config_1.yaml").write_text(_PRESET.format(d=d))
        for res in ("320240", "240320"):
            (Path(d) / res).mkdir()
        cfg = {"paths": {"service_config": d, "themes_dir": str(Path(d) / "presets"),
                         "backgrounds_dir": d},
               "supported_formats": {"images": [".png"]}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=None)

    def test_selecting_preset_keeps_rotation(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.set_rotation(90)
            self.assertEqual(be.current_rotation, 90)

            be.select_theme(str(Path(d) / "presets" / "240320" / "config_1.yaml"))

            self.assertEqual(be.current_rotation, 90)          # not reset to 0
            self.assertIn("240320", be.preview_manager.current_background_path)


if __name__ == "__main__":
    unittest.main()
