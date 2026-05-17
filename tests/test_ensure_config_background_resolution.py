# SPDX-License-Identifier: Apache-2.0
"""Regression test: _ensure_config_background() must resolve the active
config's {resolution} placeholder (with rotation-aware swap) before checking/
downloading the background — a manual, un-templated YAML read was a no-op at
best and, after config_generator.py started saving background paths with a
literal {resolution} placeholder, actively created a bogus "{resolution}"
directory on disk instead of finding the real missing video.
"""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

_CONFIG_YAML_TEMPLATE = """\
display:
  rotation: 0
  background:
    path: "{bg_dir}/{{resolution}}/a001.mp4"
    type: video
  foreground:
    enabled: false
    path: ""
    position: {{x: 0, y: 0}}
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


class TestEnsureConfigBackgroundResolution(unittest.TestCase):
    def setUp(self):
        _app()

    def test_ensure_config_background_resolves_placeholder_not_literal(self):
        with TemporaryDirectory() as cfg_dir:
            from thermalright_lcd_control.gui.backend.app_backend import AppBackend
            config_path = Path(cfg_dir) / "config_dev1.yaml"
            config_path.write_text(_CONFIG_YAML_TEMPLATE.format(bg_dir=cfg_dir))
            cfg = {"paths": {"service_config": cfg_dir,
                             "themes_dir": cfg_dir, "backgrounds_dir": cfg_dir},
                   "supported_formats": {}}

            with patch(
                "thermalright_lcd_control.device_controller.display.asset_download."
                "ensure_background_downloaded"
            ) as mock_ensure:
                AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                  "width": 320, "height": 240}], event_bus=None)

                mock_ensure.assert_called_once()
                resolved_path = mock_ensure.call_args[0][0]
                self.assertNotIn("{resolution}", resolved_path)
                self.assertIn("320240", resolved_path)

            # No bogus literal "{resolution}" directory must have been created.
            self.assertFalse((Path(cfg_dir) / "{resolution}").exists())


if __name__ == "__main__":
    unittest.main()
