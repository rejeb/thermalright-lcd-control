# SPDX-License-Identifier: Apache-2.0
"""Rotating to a new orientation drops the current theme for the first preset.

When the device is rotated and the orientation flips (landscape ↔ portrait), the
current theme no longer corresponds to the new orientation, so reload_for_device
selects the first preset of the new orientation into the live preview. Rotation is
NOT auto-saved: the active config on disk stays untouched until the user saves.
"""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.device_controller.display import vips_utils as vu  # noqa: E402

_HEAD = """\
display:
  rotation: 0
  background: {{path: "{d}/{{resolution}}/{bg}", type: image}}
  foreground: {{enabled: false, path: "", position: {{x: 0, y: 0}}, alpha: 1.0}}
  metrics: {{enabled: false, configs: []}}
  date: {{enabled: false}}
  time: {{enabled: false}}
  texts: []
"""


def _app():
    return QApplication.instance() or QApplication([])


class TestRotationLoadsFirstPreset(unittest.TestCase):
    def setUp(self):
        _app()

    def _window(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        from thermalright_lcd_control.gui.native.main_window import NativeMainWindow
        from thermalright_lcd_control.gui.native.tabs import SideTabs

        # active config uses a001.png; presets use p001.png so the persisted
        # config can be told apart from the pre-rotation one.
        Path(d, "config_dev1.yaml").write_text(_HEAD.format(d=d, bg="a001.png"))
        pr = Path(d, "presets")
        for res, (w, h) in (("320240", (320, 240)), ("240320", (240, 320))):
            (pr / res).mkdir(parents=True)
            Path(d, res).mkdir()
            for name in ("a001.png", "p001.png"):
                vu.to_rgb(vu.solid(w, h, (1, 2, 3, 255))).write_to_file(str(Path(d, res, name)))
            (pr / res / "preset_a.yaml").write_text(_HEAD.format(d=d, bg="p001.png"))
        cfg = {"paths": {"service_config": d, "themes_dir": str(pr), "backgrounds_dir": d},
               "supported_formats": {"images": [".png"]}}
        be = AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                               "width": 320, "height": 240}], event_bus=None)

        win = NativeMainWindow.__new__(NativeMainWindow)   # bypass full Qt init
        win.backend = be
        win.tabs = SideTabs(be)
        win.preview = mock.MagicMock()
        win.editor = mock.MagicMock()
        win._last_media_res = None
        be.device_changed.connect(win.reload_for_device)
        return win, be

    def test_orientation_flip_selects_first_preset_without_persisting(self):
        with TemporaryDirectory() as d:
            win, be = self._window(d)
            win.reload_for_device()                    # initial (device switch)

            first_preset = be._display_name(be._yaml_files()[0])
            be.set_rotation(90)                         # landscape → portrait

            # In-memory state reflects the new orientation + first preset...
            self.assertEqual(be.current_rotation, 90)
            self.assertEqual(be.current_theme_name, first_preset)
            # ...but rotation is NOT auto-saved: the active config on disk is
            # unchanged (still the pre-rotation a001.png at rotation 0).
            active = Path(d, "config_dev1.yaml").read_text()
            self.assertIn("a001.png", active)
            self.assertNotIn("p001.png", active)
            self.assertIn("rotation: 0", active)


if __name__ == "__main__":
    unittest.main()
