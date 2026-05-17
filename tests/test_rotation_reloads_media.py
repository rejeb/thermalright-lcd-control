# SPDX-License-Identifier: Apache-2.0
"""Regression test: rotating the device must reload the background/foreground
media for the new (rotation-swapped) resolution folder, not keep showing the
media resolved for the previous orientation.

Root cause: the reentrant reload triggered by set_rotation() (via
_sync_rotation_dirs -> device_changed -> select_theme()) loaded the active
config's background/foreground paths using ConfigLoader with the *file's own*
(stale, not-yet-saved) rotation field, so {resolution} kept templating to the
old folder even though the rotation button/media-browsing dirs had already
moved to the new one.
"""
import os
import unittest
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

_CONFIG_YAML_TEMPLATE = """\
display:
  rotation: 0
  background:
    path: "{bg_dir}/{{resolution}}/a001.png"
    type: image
  foreground:
    enabled: true
    path: "{bg_dir}/{{resolution}}/fg.png"
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


class TestRotationReloadsMedia(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, cfg_dir):
        from pathlib import Path

        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        (Path(cfg_dir) / "config_dev1.yaml").write_text(
            _CONFIG_YAML_TEMPLATE.format(bg_dir=cfg_dir))
        cfg = {"paths": {"service_config": cfg_dir,
                         "themes_dir": cfg_dir, "backgrounds_dir": cfg_dir},
               "supported_formats": {}}
        be = AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                               "width": 320, "height": 240}], event_bus=None)

        # Same wiring as main_window.py: device_changed -> reload_for_device()
        # -> select_theme(active_config) — the device's active config is loaded
        # into the preview directly (no "Current" tile in the themes grid).
        def _reload_for_device():
            active = be._active_config_file()
            if active is not None:
                be.select_theme(str(active))
        be.device_changed.connect(_reload_for_device)
        # Initial load, same as main_window.py calling reload_for_device() on startup.
        _reload_for_device()
        return be

    def test_set_rotation_reloads_background_and_foreground_for_new_folder(self):
        with TemporaryDirectory() as cfg_dir:
            be = self._backend(cfg_dir)
            self.assertIn("320240", be.preview_manager.current_background_path)
            self.assertIn("320240", be.preview_manager.current_foreground_path)

            be.set_rotation(90)

            self.assertIn("240320", be.preview_manager.current_background_path)
            self.assertIn("240320", be.preview_manager.current_foreground_path)


if __name__ == "__main__":
    unittest.main()
