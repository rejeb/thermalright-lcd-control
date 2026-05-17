# SPDX-License-Identifier: Apache-2.0
"""A device's config is read from disk only on its first load; switching back to
an already-loaded device restores its in-memory state (including unsaved runtime
edits) without re-reading the disk file."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

DEV1 = {"id": "dev1", "vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240}
DEV2 = {"id": "dev2", "vid": 0x0416, "pid": 0x5408, "width": 1920, "height": 440}

_CONFIG = """\
display:
  rotation: 0
  background: {{path: "{bg}", type: image}}
  foreground: {{enabled: false, path: "", position: {{x: 0, y: 0}}, alpha: 1.0}}
  metrics: {{enabled: false, configs: []}}
  date: {{enabled: false}}
  time: {{enabled: false}}
  texts: []
"""


def _app():
    return QApplication.instance() or QApplication([])


class TestInMemoryConfigAcrossSwitch(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        Path(d, "config_dev1.yaml").write_text(_CONFIG.format(bg=f"{d}/disk1.png"))
        Path(d, "config_dev2.yaml").write_text(_CONFIG.format(bg=f"{d}/disk2.png"))
        for name in ("disk1.png", "disk2.png", "edited.png"):
            Path(d, name).write_bytes(b"")
        cfg = {"paths": {"service_config": d, "themes_dir": d, "backgrounds_dir": d},
               "supported_formats": {"images": [".png"]}}
        be = AppBackend(cfg, [DEV1, DEV2], event_bus=None)

        # mirror main_window.reload_for_device: restore from memory if the device
        # was already loaded, else read its active config from disk once.
        def _reload():
            if be.has_device_state():
                be.restore_device_state()
            else:
                active = be._active_config_file()
                if active is not None:
                    be.select_theme(str(active))
        be.device_changed.connect(_reload)
        _reload()                       # startup: first load of dev1 from disk
        return be

    def test_switch_back_restores_inmemory_edit_without_disk(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            self.assertIn("disk1", be.preview_manager.current_background_path)

            # Edit dev1 in memory (pick a different background) — no save.
            be.select_background(f"{d}/edited.png")
            self.assertIn("edited", be.preview_manager.current_background_path)

            be.select_device(be._device_key(DEV2))      # first load of dev2 (disk)
            self.assertIn("disk2", be.preview_manager.current_background_path)

            # Switching back must restore dev1's edited (in-memory) background, not
            # the disk value — and must not read any config file from disk.
            from thermalright_lcd_control.device_controller.display import config_loader
            with mock.patch.object(
                    config_loader.ConfigLoader, "load_config",
                    side_effect=AssertionError("disk config read on switch back")):
                be.select_device(be._device_key(DEV1))
            self.assertIn("edited", be.preview_manager.current_background_path)

    def test_disk_file_untouched_by_switch(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            be.select_background(f"{d}/edited.png")
            be.select_device(be._device_key(DEV2))
            be.select_device(be._device_key(DEV1))
            # The edit lived only in memory; dev1's config file still points at disk1.
            self.assertIn("disk1.png", Path(d, "config_dev1.yaml").read_text())
            self.assertNotIn("edited.png", Path(d, "config_dev1.yaml").read_text())


if __name__ == "__main__":
    unittest.main()
