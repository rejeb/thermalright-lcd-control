# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app():
    return QApplication.instance() or QApplication([])


class TestDeviceRestart(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, controller):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}],
                          event_bus=None, controller=controller)

    def test_first_device_added_becomes_active(self):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        be = AppBackend(cfg, [], event_bus=None, controller=mock.MagicMock())  # no device
        self.assertEqual(be.device, {})
        changed = []
        be.device_changed.connect(lambda: changed.append(1))
        entry = {"id": "dev1", "vid": "0x0416", "pid": "0x5302",
                 "width": 320, "height": 240, "generic": True}
        with mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.build_device_entry", return_value=entry), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.write_device_entry"), \
             mock.patch.object(be, "_load_devices_yaml", return_value=[entry]), \
             mock.patch.object(be, "_resolution_supported", return_value=True), \
             mock.patch("thermalright_lcd_control.gui.backend.app_backend."
                        "user_backgrounds.materialize_for"):
            be.add_device("{}")
        self.assertEqual(be.device.get("id"), "dev1")   # first device activated
        self.assertTrue(changed)                          # GUI reloads for it

    def test_add_device_builds_only_new_engine(self):
        controller = mock.MagicMock()
        be = self._backend(controller)
        entry = {"id": "dev2", "vid": "0x0416", "pid": "0x5408",
                 "width": 480, "height": 480, "generic": False}
        with mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.build_device_entry", return_value=entry), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.write_device_entry"), \
             mock.patch.object(be, "_load_devices_yaml", return_value=[entry]), \
             mock.patch.object(be, "_resolution_supported", return_value=True), \
             mock.patch("thermalright_lcd_control.gui.backend.app_backend."
                        "user_backgrounds.materialize_for"):
            res = be.add_device("{}")
        self.assertIn('"success": true', res)
        controller.add_device_engine.assert_called_once_with("dev2")
        controller.restart_async.assert_not_called()

    def test_delete_active_device_syncs_controller_active_id(self):
        import tempfile
        controller = mock.MagicMock()
        controller.active_device_id = "dev1"
        be = self._backend(controller)      # active device = dev1
        remaining = {"id": "dev2", "vid": "0x0416", "pid": "0x5408",
                     "width": 480, "height": 480, "generic": True}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(be, "_config_dir", return_value=tmp), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.remove_device_entry"), \
             mock.patch.object(be, "_load_devices_yaml", return_value=[remaining]), \
             mock.patch.object(be, "_ensure_active_config"):
            res = be.delete_device("dev1")
        self.assertIn('"success": true', res)
        self.assertEqual(be.device.get("id"), "dev2")
        # the remaining engines must preview dev2, not the deleted dev1
        self.assertEqual(controller.active_device_id, "dev2")
        controller.remove_device_engine.assert_called_once_with("dev1")
        controller.restart_async.assert_not_called()

    def test_update_active_device_id_rename_syncs_controller(self):
        import tempfile
        controller = mock.MagicMock()
        controller.active_device_id = "dev1"
        be = self._backend(controller)      # active device = dev1
        entry = {"id": "dev1b", "vid": "0x0416", "pid": "0x5302",
                 "width": 320, "height": 240, "generic": True}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(be, "_config_dir", return_value=tmp), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.build_device_entry", return_value=entry), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.update_device_entry"), \
             mock.patch.object(be, "_load_devices_yaml", return_value=[entry]), \
             mock.patch.object(be, "_resolution_supported", return_value=True), \
             mock.patch.object(be, "_ensure_active_config"), \
             mock.patch("thermalright_lcd_control.gui.backend.app_backend."
                        "user_backgrounds.materialize_for"):
            res = be.update_device("dev1", "{}")
        self.assertIn('"success": true', res)
        self.assertEqual(controller.active_device_id, "dev1b")
        controller.update_device_engine.assert_called_once_with("dev1", "dev1b")
        controller.restart_async.assert_not_called()


if __name__ == "__main__":
    unittest.main()
