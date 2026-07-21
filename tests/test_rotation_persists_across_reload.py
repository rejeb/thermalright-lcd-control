# SPDX-License-Identifier: Apache-2.0
"""Regression test: rotating the device must not be silently reset back to 0°.

``set_rotation()`` changes the media folders (``_media_res()`` swaps for
90/270), which makes ``_sync_rotation_dirs()`` emit ``device_changed`` — wired
by ``main_window.py`` to ``reload_for_device()`` -> ``select_theme()`` on the
active config. Since the active config's ``rotation`` field on disk hasn't
been saved yet, a naive ``select_theme()`` stomps ``current_rotation`` back to
0 within the same click, before the user can see it or save it. This test
reproduces that exact reentrant chain (the same wiring ``main_window.py``
sets up) without needing a real window.
"""
import os
import unittest
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

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


class TestRotationPersistsAcrossReload(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, cfg_dir):
        from pathlib import Path

        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        (Path(cfg_dir) / "config_dev1.yaml").write_text(_CONFIG_YAML)
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
        return be

    def test_set_rotation_survives_the_reentrant_theme_reload(self):
        with TemporaryDirectory() as cfg_dir:
            be = self._backend(cfg_dir)
            self.assertEqual(be.current_rotation, 0)

            be.set_rotation(90)

            self.assertEqual(be.current_rotation, 90)
            self.assertEqual(be.preview_manager.current_rotation, 90)


if __name__ == "__main__":
    unittest.main()
