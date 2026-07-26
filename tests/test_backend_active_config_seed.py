# SPDX-License-Identifier: Apache-2.0
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.display import vips_utils as vu

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


class TestNoDeviceThemes(unittest.TestCase):
    def setUp(self):
        _app()

    def test_get_themes_empty_when_no_device(self):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        with TemporaryDirectory() as cfg_dir:
            # a leftover resolution-keyed config exists but must NOT surface
            (Path(cfg_dir) / "config_no_device.yaml").write_text(_PRESET_YAML)
            cfg = {"paths": {"service_config": cfg_dir}, "supported_formats": {}}
            be = AppBackend(cfg, [], event_bus=None)   # no device
            self.assertEqual(json.loads(be.get_themes()), [])


class TestActiveConfigSeed(unittest.TestCase):
    def setUp(self):
        _app()

    def _paths(self, root):
        return {
            "service_config": str(root / "config"),
            "themes_dir": str(root / "themes"),
            "backgrounds_dir": str(root / "bg"),
            "foregrounds_dir": str(root / "fg"),
        }

    def test_seed_from_first_preset(self):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            (root / "config").mkdir()
            (root / "themes" / "320240").mkdir(parents=True)
            (root / "themes" / "320240" / "config_1.yaml").write_text(_PRESET_YAML)
            cfg = {"paths": self._paths(root),
                   "supported_formats": {"images": [".png"]}}
            AppBackend(cfg, [{"id": "dev1", "vid": 0x416, "pid": 0x5302,
                              "width": 320, "height": 240}], event_bus=None)
            active = root / "config" / "config_dev1.yaml"
            self.assertTrue(active.exists())            # seeded
            self.assertIn("preset.png", active.read_text())

    def test_seed_from_first_background_when_no_preset(self):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            (root / "config").mkdir()
            bgdir = root / "bg" / "320240"; bgdir.mkdir(parents=True)
            vu.to_rgb(vu.solid(8, 8, (0, 0, 0, 255))).write_to_file(str(bgdir / "z_first.png"))
            cfg = {"paths": self._paths(root),
                   "supported_formats": {"images": [".png"], "videos": [], "gifs": []}}
            AppBackend(cfg, [{"id": "dev1", "vid": 0x416, "pid": 0x5302,
                              "width": 320, "height": 240}], event_bus=None)
            active = root / "config" / "config_dev1.yaml"
            self.assertTrue(active.exists())            # seeded from background
            self.assertIn("z_first.png", active.read_text())

    def test_seeds_every_device_not_just_active(self):
        # Two configured devices (e.g. both auto-detected on first launch):
        # each must get its own active config at init, otherwise the non-active
        # device's RenderEngine fails to build (missing config_<id>.yaml) and it
        # gets no generator — the preview then keeps showing the active device.
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            (root / "config").mkdir()
            (root / "themes" / "320240").mkdir(parents=True)
            (root / "themes" / "320240" / "config_1.yaml").write_text(_PRESET_YAML)
            cfg = {"paths": self._paths(root),
                   "supported_formats": {"images": [".png"]}}
            AppBackend(cfg, [
                {"id": "dev1", "vid": 0x416, "pid": 0x5302,
                 "width": 320, "height": 240},
                {"id": "dev2", "vid": 0x416, "pid": 0x5408,
                 "width": 320, "height": 240},
            ], event_bus=None)
            self.assertTrue((root / "config" / "config_dev1.yaml").exists())
            self.assertTrue((root / "config" / "config_dev2.yaml").exists())

    def test_no_seed_when_no_preset_and_no_background(self):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        with TemporaryDirectory() as root_s:
            root = Path(root_s)
            (root / "config").mkdir()
            cfg = {"paths": self._paths(root),
                   "supported_formats": {"images": [".png"]}}
            AppBackend(cfg, [{"id": "dev1", "vid": 0x416, "pid": 0x5302,
                              "width": 320, "height": 240}], event_bus=None)
            self.assertFalse((root / "config" / "config_dev1.yaml").exists())


if __name__ == "__main__":
    unittest.main()
