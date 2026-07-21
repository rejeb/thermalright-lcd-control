# SPDX-License-Identifier: Apache-2.0
"""Add/edit device form: the Native/Generic driver-mode choice is only shown
for devices that actually have a native (legacy) driver class for their
(vid, pid, width, height); otherwise Generic is the only mode and is forced."""
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _backend():
    from thermalright_lcd_control.gui.backend.app_backend import AppBackend
    cfg = {"paths": {"backgrounds_dir": "resources/themes/backgrounds"},
           "supported_formats": {}}
    return AppBackend(cfg, [], event_bus=None)


class TestCheckNativeDriver(unittest.TestCase):
    def setUp(self):
        _app()
        self.backend = _backend()

    def _available(self, vid, pid, w, h):
        return json.loads(
            self.backend.check_native_driver(vid, pid, w, h))["available"]

    def test_known_native_device(self):
        self.assertTrue(self._available("0x0416", "0x5302", "320", "240"))

    def test_same_vid_pid_other_resolution(self):
        self.assertFalse(self._available("0x0416", "0x5302", "480", "480"))

    def test_unknown_device(self):
        self.assertFalse(self._available("0x1234", "0x5678", "320", "240"))
        self.assertFalse(self._available("", "", "320", "240"))


class TestDeviceDialogDriverVisibility(unittest.TestCase):
    def setUp(self):
        _app()
        self.backend = _backend()

    def test_hidden_and_forced_generic_for_device_without_native_driver(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend, edit_config={
            "id": "dev1", "vid": "0x0416", "pid": "0x5408",
            "width": 480, "height": 480, "generic": False})
        self.assertTrue(dlg._driver_row.isHidden())
        self.assertEqual(dlg._driver, "generic")
        dlg.deleteLater()

    def test_visible_for_device_with_native_driver(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend, edit_config={
            "id": "dev1", "vid": "0x0416", "pid": "0x5302",
            "width": 320, "height": 240, "generic": False})
        self.assertFalse(dlg._driver_row.isHidden())
        self.assertEqual(dlg._driver, "native")
        dlg.deleteLater()

    def test_visibility_follows_vid_pid_edits(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend, edit_config={
            "id": "dev1", "vid": "0x0416", "pid": "0x5302",
            "width": 320, "height": 240})
        self.assertFalse(dlg._driver_row.isHidden())
        dlg._inputs["pid"].setText("0x9999")
        dlg._inputs["pid"].textEdited.emit("0x9999")   # setText n'émet pas textEdited
        self.assertTrue(dlg._driver_row.isHidden())
        dlg.deleteLater()

    def test_visibility_follows_resolution_change(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend, edit_config={
            "id": "dev1", "vid": "0x0416", "pid": "0x5302",
            "width": 320, "height": 240})
        self.assertFalse(dlg._driver_row.isHidden())
        dlg._set_resolution(480, 480)   # pas de classe native 5302 en 480x480
        self.assertTrue(dlg._driver_row.isHidden())
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
