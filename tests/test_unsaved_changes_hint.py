# SPDX-License-Identifier: Apache-2.0
"""The 'Save config' hint: editing the current theme marks the config dirty
(unsaved_changes_changed=True); saving (apply) or loading the device's own active
config clears it."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.device_controller.display.event_bus import EventBus  # noqa: E402

_CONFIG = """\
display:
  rotation: 0
  background: {path: "", type: image}
  foreground: {enabled: false, path: "", position: {x: 0, y: 0}, alpha: 1.0}
  metrics: {enabled: false, configs: []}
  date: {enabled: false}
  time: {enabled: false}
  texts: []
"""


def _app():
    return QApplication.instance() or QApplication([])


class TestUnsavedChangesHint(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        self.presets = Path(d, "presets", "320240")
        self.presets.mkdir(parents=True)
        (self.presets / "theme_1.yaml").write_text(_CONFIG)
        (self.presets / "theme_2.yaml").write_text(_CONFIG)
        Path(d, "config_dev1.yaml").write_text(_CONFIG)
        Path(d, "bg.png").write_bytes(b"")
        cfg = {"paths": {"service_config": d,
                         "themes_dir": str(Path(d, "presets")), "backgrounds_dir": d},
               "supported_formats": {"images": [".png"]}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=EventBus())

    def test_fresh_backend_is_clean(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            self.assertFalse(be._dirty)

    def test_loading_active_config_stays_clean(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.select_theme(str(be._active_config_file()))
            self.assertFalse(be._dirty)

    def test_picking_other_theme_marks_dirty(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.select_theme(str(be._active_config_file()))
            be.select_theme(str(self.presets / "theme_2.yaml"))
            self.assertTrue(be._dirty)

    def test_edit_marks_dirty_and_save_clears_it(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            emitted = []
            be.unsaved_changes_changed.connect(lambda v: emitted.append(v))
            be.select_background(str(Path(d, "bg.png")))
            self.assertTrue(be._dirty)
            be.apply()                       # "Save config"
            self.assertFalse(be._dirty)
            self.assertEqual(emitted[-2:], [True, False])


if __name__ == "__main__":
    unittest.main()
