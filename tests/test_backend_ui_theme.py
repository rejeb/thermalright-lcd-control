# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app():
    return QApplication.instance() or QApplication([])


class TestUiTheme(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, cfg_dir, config_path=None, theme=None):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {"service_config": cfg_dir,
                         "themes_dir": cfg_dir, "backgrounds_dir": cfg_dir},
               "supported_formats": {}}
        if theme is not None:
            cfg["ui"] = {"theme": theme}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=None,
                          config_path=config_path)

    def test_default_theme_is_dark(self):
        with TemporaryDirectory() as cfg_dir:
            be = self._backend(cfg_dir)
            self.assertEqual(be.get_ui_theme(), "dark")

    def test_get_reads_config(self):
        with TemporaryDirectory() as cfg_dir:
            be = self._backend(cfg_dir, theme="light")
            self.assertEqual(be.get_ui_theme(), "light")

    def test_invalid_theme_falls_back_to_dark(self):
        with TemporaryDirectory() as cfg_dir:
            be = self._backend(cfg_dir, theme="neon")
            self.assertEqual(be.get_ui_theme(), "dark")

    def test_set_persists_to_yaml(self):
        with TemporaryDirectory() as cfg_dir:
            path = Path(cfg_dir) / "gui_config.yaml"
            path.write_text("paths: {}\n")
            be = self._backend(cfg_dir, config_path=str(path))
            be.set_ui_theme("dark")
            self.assertEqual(be.get_ui_theme(), "dark")
            data = yaml.safe_load(path.read_text())
            self.assertEqual(data["ui"]["theme"], "dark")
            # existing keys preserved
            self.assertIn("paths", data)

    def test_set_invalid_normalised_to_dark(self):
        with TemporaryDirectory() as cfg_dir:
            path = Path(cfg_dir) / "gui_config.yaml"
            be = self._backend(cfg_dir, config_path=str(path))
            be.set_ui_theme("bogus")
            self.assertEqual(be.get_ui_theme(), "dark")


if __name__ == "__main__":
    unittest.main()
