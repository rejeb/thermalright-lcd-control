# SPDX-License-Identifier: Apache-2.0
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

_CONFIG_YAML = """\
display:
  rotation: 0
  background:
    path: ""
    type: image
  foreground:
    enabled: false
    path: ""
    position: {x: 0, y: 0}
    alpha: 1.0
  metrics:
    enabled: false
    configs: []
  date:
    enabled: false
  time:
    enabled: false
  texts: []
"""


def _app():
    return QApplication.instance() or QApplication([])


class TestCurrentTheme(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, cfg_dir):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        # Point themes/backgrounds at the (empty) cfg_dir so the active-config
        # seeding has nothing to seed from — these tests isolate the "current
        # theme" listing, not the seeding behaviour (covered elsewhere).
        cfg = {"paths": {"service_config": cfg_dir,
                         "themes_dir": cfg_dir, "backgrounds_dir": cfg_dir},
               "supported_formats": {}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=None)

    def test_no_current_tile_even_when_config_exists(self):
        # The device's active config is loaded into the preview on startup but is
        # no longer surfaced as a "Current" tile in the themes grid.
        with TemporaryDirectory() as cfg_dir:
            (Path(cfg_dir) / "config_dev1.yaml").write_text(_CONFIG_YAML)
            be = self._backend(cfg_dir)
            themes = json.loads(be.get_themes())
            self.assertFalse(any(t["name"] == "Current" for t in themes))

    def test_no_current_theme_when_config_absent(self):
        with TemporaryDirectory() as cfg_dir:
            be = self._backend(cfg_dir)
            themes = json.loads(be.get_themes())
            self.assertFalse(any(t["name"] == "Current" for t in themes))


if __name__ == "__main__":
    unittest.main()
