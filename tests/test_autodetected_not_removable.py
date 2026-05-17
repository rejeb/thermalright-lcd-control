# SPDX-License-Identifier: Apache-2.0
"""Auto-detected devices (startup probe) are not user-removable: the registry
marks them, the backend refuses the delete, and the titlebar disables 🗑."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.display import device_registry


def _app():
    return QApplication.instance() or QApplication([])


class TestRegistryFlag(unittest.TestCase):
    _FORM = {"id": "dev1", "vid": "0x0416", "pid": "0x5302",
             "width": 320, "height": 240, "transport": "hid",
             "encoding": "rgb565_le_columns"}

    def test_build_entry_keeps_auto_detected_flag(self):
        entry = device_registry.build_device_entry(
            dict(self._FORM, auto_detected=True))
        self.assertTrue(entry["auto_detected"])

    def test_user_added_entry_has_no_flag(self):
        entry = device_registry.build_device_entry(dict(self._FORM))
        self.assertNotIn("auto_detected", entry)

    def test_register_detected_devices_sets_flag(self):
        reg = {"vid": 0x0416, "pid": 0x5302, "wire": "hid"}
        detected = {"detected": True, "config": dict(self._FORM)}
        written = []
        with mock.patch.object(device_registry, "list_devices", return_value=[]), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "probe_registry.load_registry", return_value=[reg]), \
             mock.patch.object(device_registry, "detect_device",
                               return_value=detected), \
             mock.patch.object(device_registry, "write_device_entry",
                               side_effect=lambda _dir, e: written.append(e)):
            added = device_registry.register_detected_devices(
                "/tmp/cfg", find=lambda **kw: [mock.MagicMock(bus=3, address=4)])
        self.assertEqual(len(added), 1)
        self.assertTrue(written[0]["auto_detected"])


class TestBackendRefusesDelete(unittest.TestCase):
    def setUp(self):
        _app()
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        self.auto = {"id": "auto1", "vid": 0x0416, "pid": 0x5408,
                     "width": 1920, "height": 440, "auto_detected": True}
        self.manual = {"id": "man1", "vid": 0x0416, "pid": 0x5302,
                       "width": 320, "height": 240}
        self.be = AppBackend(cfg, [self.auto, self.manual],
                             event_bus=None, controller=mock.MagicMock())

    def test_get_devices_exposes_auto_flag(self):
        devs = {d["id"]: d for d in json.loads(self.be.get_devices())}
        self.assertTrue(devs["auto1"]["auto"])
        self.assertFalse(devs["man1"]["auto"])

    def test_edit_preserves_auto_flag(self):
        import tempfile
        form = {"id": "auto1", "vid": "0x0416", "pid": "0x5408",
                "width": 1920, "height": 440, "transport": "usb_bulk_ly",
                "encoding": "jpeg"}
        captured = {}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(self.be, "_config_dir", return_value=tmp), \
             mock.patch.object(self.be, "_resolution_supported", return_value=True), \
             mock.patch.object(self.be, "_load_devices_yaml",
                               return_value=[self.auto, self.manual]), \
             mock.patch.object(self.be, "_ensure_active_config"), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.update_device_entry",
                        side_effect=lambda _d, _o, e: captured.update(e)), \
             mock.patch("thermalright_lcd_control.gui.backend.app_backend."
                        "user_backgrounds.materialize_for"):
            res = json.loads(self.be.update_device("auto1", json.dumps(form)))
        self.assertTrue(res["success"])
        self.assertTrue(captured.get("auto_detected"))   # flag survives the edit

    def test_delete_auto_detected_refused(self):
        with mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.remove_device_entry") as rm:
            res = json.loads(self.be.delete_device("auto1"))
        self.assertFalse(res["success"])
        self.assertIn("Auto-detected", res["error"])
        rm.assert_not_called()                     # nothing touched on disk


class TestTitlebarDeleteDisabled(unittest.TestCase):
    def setUp(self):
        _app()

    def _bar(self, devices):
        from thermalright_lcd_control.gui.native.titlebar import TitleBar
        be = mock.MagicMock()
        be.config = {"paths": {}}
        be.get_devices.return_value = json.dumps(devices)
        be.get_ui_theme.return_value = "dark"
        return TitleBar(be)

    def test_delete_hidden_on_auto_tab_shown_on_manual(self):
        bar = self._bar([
            {"key": "auto1", "label": "Auto", "id": "auto1",
             "auto": True, "current": True},
            {"key": "man1", "label": "Manual", "id": "man1", "auto": False},
        ])
        # 🗑 lives on the active tab, hidden for auto-detected devices
        self.assertFalse(bar._tab_del_btn.isVisibleTo(bar._tab_btns))
        bar.device_tabs.setCurrentIndex(1)
        self.assertTrue(bar._tab_del_btn.isVisibleTo(bar._tab_btns))

    def test_no_tab_buttons_on_placeholder(self):
        from PySide6.QtWidgets import QTabBar
        bar = self._bar([])
        self.assertIsNone(bar.device_tabs.tabButton(0, QTabBar.RightSide))


if __name__ == "__main__":
    unittest.main()
