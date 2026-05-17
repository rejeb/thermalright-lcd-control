# SPDX-License-Identifier: Apache-2.0
"""A user pick in the themes grid saves the theme as the device's current
config immediately (select_theme persist=True → apply); programmatic reloads
(persist=False) do not."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

_PRESET_YAML = """\
display:
  rotation: 0
  background:
    path: ./resources/themes/backgrounds/{resolution}/preset.png
    type: image
  foreground: {enabled: false, path: "", position: {x: 0, y: 0}, alpha: 1.0}
  metrics: {enabled: false, configs: []}
  date: {enabled: false}
  time: {enabled: false}
  texts: []
"""


def _app():
    return QApplication.instance() or QApplication([])


class TestSelectThemePersists(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, root: Path):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        (root / "config").mkdir()
        (root / "themes" / "320240").mkdir(parents=True)
        (root / "themes" / "320240" / "config_1.yaml").write_text(_PRESET_YAML)
        cfg = {"paths": {
            "service_config": str(root / "config"),
            "themes_dir": str(root / "themes"),
            "backgrounds_dir": str(root / "bg"),
            "foregrounds_dir": str(root / "fg"),
        }, "supported_formats": {"images": [".png"]}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=None)

    def test_user_pick_saves_current_config(self):
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            be = self._backend(root)
            preset = str((root / "themes" / "320240" / "config_1.yaml").resolve())
            with mock.patch.object(be, "apply") as apply_mock:
                be.select_theme(preset, persist=True)
                apply_mock.assert_called_once()

    def test_programmatic_reload_does_not_save(self):
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            be = self._backend(root)
            preset = str((root / "themes" / "320240" / "config_1.yaml").resolve())
            with mock.patch.object(be, "apply") as apply_mock:
                be.select_theme(preset)                 # default persist=False
                apply_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
