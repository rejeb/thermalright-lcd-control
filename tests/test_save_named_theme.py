# SPDX-License-Identifier: Apache-2.0
"""Saving a named theme (the "Save theme" export field): writes user_<slug>.yaml,
refuses to overwrite a bundled default theme, and confirms before overwriting an
existing user theme."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

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


class TestSaveNamedTheme(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        self.presets = Path(d, "presets", "320240")
        self.presets.mkdir(parents=True)
        (self.presets / "theme_1.yaml").write_text(_CONFIG)     # bundled default
        cfg = {"paths": {"service_config": d,
                         "themes_dir": str(Path(d, "presets")), "backgrounds_dir": d},
               "supported_formats": {"images": [".png"]}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=None)

    def test_new_name_writes_user_theme_file(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            res = json.loads(be.save_theme("My Cool Theme"))
            self.assertTrue(res["success"])
            self.assertTrue((self.presets / "user_my_cool_theme.yaml").exists())

    def test_empty_name_rejected(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            res = json.loads(be.save_theme("   "))
            self.assertFalse(res["success"])
            self.assertIn("name", res["error"].lower())

    def test_cannot_overwrite_bundled_default(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            res = json.loads(be.save_theme("Theme 1"))   # matches theme_1.yaml
            self.assertFalse(res["success"])
            self.assertIn("built-in", res["error"])
            # the default file is untouched (no user_ file created for it)
            self.assertFalse((self.presets / "user_theme_1.yaml").exists())

    def test_overwrite_user_theme_confirmed(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.save_theme("My Theme")
            with mock.patch.object(be, "_confirm", return_value=True) as q:
                res = json.loads(be.save_theme("My Theme"))
            q.assert_called_once()
            self.assertTrue(res["success"])

    def test_overwrite_user_theme_cancelled(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.save_theme("My Theme")
            with mock.patch.object(be, "_confirm", return_value=False):
                res = json.loads(be.save_theme("My Theme"))
            self.assertFalse(res["success"])
            self.assertTrue(res["cancelled"])

    def test_user_theme_is_removable_and_displays_clean_name(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.save_theme("My Theme")
            f = self.presets / "user_my_theme.yaml"
            self.assertTrue(be._is_user_theme(f))
            self.assertEqual(be._display_name(f), "My Theme")


if __name__ == "__main__":
    unittest.main()
