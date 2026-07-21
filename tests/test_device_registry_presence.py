# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display import device_registry


class TestPresentDeviceIds(unittest.TestCase):
    def _entries(self):
        return [
            {"id": "dev1", "vid": "0x0416", "pid": "0x5302", "width": 320, "height": 240},
            {"id": "dev2", "vid": "0x0416", "pid": "0x5408", "width": 480, "height": 480},
        ]

    def test_only_plugged_in_devices_are_present(self):
        def fake_find(idVendor, idProduct):
            return object() if (idVendor, idProduct) == (0x0416, 0x5302) else None

        with mock.patch.object(device_registry, "list_devices", return_value=self._entries()):
            present = device_registry.present_device_ids("/cfg", find=fake_find)
        self.assertEqual(present, {"dev1"})

    def test_no_devices_present(self):
        with mock.patch.object(device_registry, "list_devices", return_value=self._entries()):
            present = device_registry.present_device_ids("/cfg", find=lambda **_: None)
        self.assertEqual(present, set())

    def test_malformed_entry_is_skipped_not_raised(self):
        entries = [{"id": "bad", "vid": "not-a-number", "pid": "0x5302"}]
        with mock.patch.object(device_registry, "list_devices", return_value=entries):
            present = device_registry.present_device_ids("/cfg", find=lambda **_: object())
        self.assertEqual(present, set())


if __name__ == "__main__":
    unittest.main()
