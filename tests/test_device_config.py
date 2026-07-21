import tempfile
import unittest
from pathlib import Path

import yaml

from thermalright_lcd_control.device_controller.display import device_config
from thermalright_lcd_control.device_controller.display.generic_device_loader import (
    parse_descriptor,
)


class TestDeviceConfigPaths(unittest.TestCase):
    def test_active_config_path_uses_id(self):
        p = device_config.active_config_path("/cfg", "ly_5408")
        self.assertEqual(p, Path("/cfg/config_ly_5408.yaml"))

    def test_legacy_config_path_uses_resolution(self):
        p = device_config.legacy_config_path("/cfg", 320, 240)
        self.assertEqual(p, Path("/cfg/config_320240.yaml"))

    def test_sanitize_id_makes_filename_safe(self):
        self.assertEqual(device_config.sanitize_id("0416:5408 @bus3"), "0416_5408_bus3")

    def test_sanitize_id_rejects_empty(self):
        with self.assertRaises(ValueError):
            device_config.sanitize_id("   ")

    def test_resolve_seeds_from_legacy_once(self):
        with tempfile.TemporaryDirectory() as d:
            legacy = device_config.legacy_config_path(d, 320, 240)
            legacy.write_text("display: {rotation: 0}\n")
            target = device_config.resolve_active_config(d, "winbond_5302", 320, 240)
            self.assertEqual(target, Path(d) / "config_winbond_5302.yaml")
            self.assertTrue(target.exists())
            # Seeding round-trips through YAML (to repair paths), so compare the
            # parsed content rather than bytes.
            self.assertEqual(yaml.safe_load(target.read_text()),
                             yaml.safe_load(legacy.read_text()))
            # legacy file is preserved (non-destructive)
            self.assertTrue(legacy.exists())

    def test_seeding_inserts_resolution_dir_in_background_path(self):
        with tempfile.TemporaryDirectory() as d:
            legacy = device_config.legacy_config_path(d, 320, 240)
            legacy.write_text(yaml.dump({"display": {"background": {
                "path": "./resources/themes/backgrounds/a001.mp4",
                "type": "video"}}}))
            target = device_config.resolve_active_config(d, "winbond_5302", 320, 240)
            data = yaml.safe_load(target.read_text())
            self.assertEqual(data["display"]["background"]["path"],
                             "./resources/themes/backgrounds/{resolution}/a001.mp4")

    def test_ensure_resolution_dir_idempotent(self):
        # Already-foldered paths (concrete dir or placeholder) are untouched.
        for p in ("./x/backgrounds/320240/a001.mp4",
                  "./x/backgrounds/{resolution}/a001.mp4"):
            self.assertEqual(device_config.ensure_resolution_dir(p, "backgrounds"), p)

    def test_resolve_no_seed_when_id_file_exists(self):
        with tempfile.TemporaryDirectory() as d:
            legacy = device_config.legacy_config_path(d, 320, 240)
            legacy.write_text("legacy\n")
            target = device_config.active_config_path(d, "winbond_5302")
            target.write_text("already there\n")
            resolved = device_config.resolve_active_config(d, "winbond_5302", 320, 240)
            self.assertEqual(resolved.read_text(), "already there\n")


class TestLoaderIdRequirement(unittest.TestCase):
    def _entry(self, **over):
        e = {"id": "x", "vid": "0x0416", "pid": "0x5302", "width": 320, "height": 240,
             "transport": "hid", "chunk_size": 4096, "encoding": "rgb565_le_columns"}
        e.update(over)
        return e

    def test_id_parsed(self):
        d = parse_descriptor(self._entry(id="winbond_5302"))
        self.assertEqual(d.id, "winbond_5302")

    def test_missing_id_raises(self):
        e = self._entry()
        del e["id"]
        with self.assertRaises(ValueError):
            parse_descriptor(e)

    def test_empty_id_raises(self):
        with self.assertRaises(ValueError):
            parse_descriptor(self._entry(id=""))


if __name__ == "__main__":
    unittest.main()
