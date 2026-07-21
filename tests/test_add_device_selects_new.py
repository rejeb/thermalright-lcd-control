# SPDX-License-Identifier: Apache-2.0
"""Regression test: adding a device must activate (select) it, even when
another device was already active — not only on a fresh install."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


class TestAddDeviceSelectsNew(unittest.TestCase):
    def setUp(self):
        _app()

    def test_new_device_becomes_active(self):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        with TemporaryDirectory() as d:
            bg = Path(d) / "backgrounds"
            for res in ("320240", "240320", "480480"):
                (bg / res).mkdir(parents=True)
            cfg_dir = Path(d) / "config"
            cfg_dir.mkdir()
            cfg = {"paths": {"backgrounds_dir": str(bg),
                             "service_config": str(cfg_dir),
                             "themes_dir": str(Path(d) / "themes")},
                   "supported_formats": {}}
            existing = {"id": "dev_old", "vid": 0x0416, "pid": 0x5302,
                        "width": 320, "height": 240}
            be = AppBackend(cfg, [existing], event_bus=None)
            self.assertEqual(be.device.get("id"), "dev_old")

            changed = []
            be.device_changed.connect(lambda: changed.append(True))
            res = json.loads(be.add_device(json.dumps({
                "id": "dev_new", "vid": "0x0416", "pid": "0x5408",
                "width": "480", "height": "480",
                "transport": "usb_bulk", "encoding": "jpeg"})))

            self.assertTrue(res.get("success"), res)
            self.assertEqual(be.device.get("id"), "dev_new")
            self.assertEqual((be.dev_width, be.dev_height), (480, 480))
            self.assertTrue(changed)
            current = [x for x in json.loads(be.get_devices()) if x["current"]]
            self.assertEqual([x["id"] for x in current], ["dev_new"])


if __name__ == "__main__":
    unittest.main()
