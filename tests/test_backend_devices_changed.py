# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


class TestDevicesChanged(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, controller=None, event_bus=None, devices=None):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        return AppBackend(cfg, devices or [], event_bus=event_bus, controller=controller)

    def test_active_device_still_present_rebinds_and_refreshes(self):
        dev1 = {"id": "dev1", "vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240}
        be = self._backend(devices=[dev1])
        refreshed = []
        be.devices_refreshed.connect(lambda: refreshed.append(1))
        new_dev1 = dict(dev1)  # fresh object, same id
        be._on_devices_changed([new_dev1])
        self.assertIs(be.device, new_dev1)
        self.assertTrue(refreshed)

    def test_active_device_removed_falls_back_to_first_remaining(self):
        dev1 = {"id": "dev1", "vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240}
        dev2 = {"id": "dev2", "vid": 0x0416, "pid": 0x5408, "width": 480, "height": 480}
        controller = mock.MagicMock()
        be = self._backend(controller=controller, devices=[dev1, dev2])
        self.assertEqual(be.device.get("id"), "dev1")
        changed = []
        be.device_changed.connect(lambda: changed.append(1))
        be._on_devices_changed([dev2])       # dev1 disappeared
        self.assertEqual(be.device.get("id"), "dev2")
        self.assertEqual(controller.active_device_id, "dev2")
        self.assertTrue(changed)

    def test_active_device_removed_no_devices_left(self):
        dev1 = {"id": "dev1", "vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240}
        controller = mock.MagicMock()
        be = self._backend(controller=controller, devices=[dev1])
        be._on_devices_changed([])
        self.assertEqual(be.device, {})
        self.assertIsNone(controller.active_device_id)

    def test_no_active_device_just_refreshes_list(self):
        be = self._backend(devices=[])
        self.assertEqual(be.device, {})
        refreshed = []
        be.devices_refreshed.connect(lambda: refreshed.append(1))
        dev1 = {"id": "dev1", "vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240}
        be._on_devices_changed([dev1])
        self.assertEqual(be.devices, [dev1])
        self.assertEqual(be.device, {})           # doesn't auto-activate a reappeared device
        self.assertTrue(refreshed)

    def test_reappeared_device_does_not_reclaim_active(self):
        dev1 = {"id": "dev1", "vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240}
        dev2 = {"id": "dev2", "vid": 0x0416, "pid": 0x5408, "width": 480, "height": 480}
        controller = mock.MagicMock()
        be = self._backend(controller=controller, devices=[dev1, dev2])
        be._on_devices_changed([dev2])            # dev1 disappears, active -> dev2
        be._on_devices_changed([dev1, dev2])       # dev1 reappears
        self.assertEqual(be.device.get("id"), "dev2")   # stays on dev2
        self.assertIn(dev1, be.devices)                  # but dev1 is back in the list

    def test_subscribes_and_unsubscribes_from_event_bus(self):
        from thermalright_lcd_control.device_controller.display.event_bus import Topic
        bus = mock.MagicMock()
        be = self._backend(event_bus=bus, devices=[])
        bus.subscribe.assert_called_once_with(Topic.DEVICES_CHANGED, be._on_devices_changed)
        be.cleanup()
        bus.unsubscribe.assert_called_once_with(Topic.DEVICES_CHANGED, be._on_devices_changed)


if __name__ == "__main__":
    unittest.main()
