# SPDX-License-Identifier: Apache-2.0
"""Rotating reloads the active theme for the new orientation.

Rotation is a per-device display change: the theme (its ``{resolution}``
background / foreground / widgets) reloads for the swapped ``<h><w>`` folder so
the preview and the grids reflect the new orientation. (This supersedes the
earlier "an unsaved background selection survives rotation" behaviour — an
explicit rotate now reloads the theme rather than preserving an in-memory
selection.)
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


class TestRotationMigratesSelectedMedia(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, cfg_dir):
        from pathlib import Path

        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        (Path(cfg_dir) / "config_dev1.yaml").write_text(
            _CONFIG_YAML_TEMPLATE.format(bg_dir=cfg_dir))
        for res in ("320240", "240320"):
            d = Path(cfg_dir) / res
            d.mkdir()
            (d / "a002.png").write_bytes(b"")
        cfg = {"paths": {"service_config": cfg_dir,
                         "themes_dir": cfg_dir, "backgrounds_dir": cfg_dir},
               "supported_formats": {"images": [".png"]}}
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
        _reload_for_device()
        return be

    def test_rotation_reloads_theme_media_for_new_orientation(self):
        with TemporaryDirectory() as cfg_dir:
            be = self._backend(cfg_dir)
            self.assertIn("320240", be.preview_manager.current_background_path)

            be.set_rotation(90)

            # The active theme reloaded for the swapped orientation folder: the
            # config's own ``{resolution}`` background (a001) now resolves to
            # ``240320`` — the preview reflects the new orientation.
            path = be.preview_manager.current_background_path
            self.assertIn("240320", path, path)
            self.assertTrue(path.endswith("a001.png"), path)


if __name__ == "__main__":
    unittest.main()
