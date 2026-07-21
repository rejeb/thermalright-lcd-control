# SPDX-License-Identifier: Apache-2.0
"""USBDeviceDetector.get_devices() must not surface a configured device that
isn't currently plugged in — otherwise the GUI's initial tab bar (built from
this list before DevicePresenceMonitor's first poll) shows a tab for
hardware that isn't there."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from thermalright_lcd_control.gui.utils.usb_detector import USBDeviceDetector


def _detector(config_dir: str) -> USBDeviceDetector:
    d = USBDeviceDetector.__new__(USBDeviceDetector)
    d.logger = mock.MagicMock()
    d.config = {"paths": {"service_config": config_dir}}
    return d


class TestPerDeviceFilesFiltered(unittest.TestCase):
    def test_only_present_devices_are_returned(self):
        entries = [{"id": "dev1", "vid": 1, "pid": 2}, {"id": "dev2", "vid": 3, "pid": 4}]
        det = _detector("/cfg")
        with mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.list_devices", return_value=entries), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.present_device_ids", return_value={"dev1"}):
            result = det.get_devices()
        self.assertEqual([d["id"] for d in result], ["dev1"])

    def test_all_absent_returns_empty_not_legacy_fallback(self):
        entries = [{"id": "dev1", "vid": 1, "pid": 2}]
        det = _detector("/cfg")
        with mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.list_devices", return_value=entries), \
             mock.patch("thermalright_lcd_control.device_controller.display."
                        "device_registry.present_device_ids", return_value=set()):
            result = det.get_devices()
        self.assertEqual(result, [])


class TestLegacyFallbackFiltered(unittest.TestCase):
    def test_legacy_device_shown_only_if_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = {"vid": "0x0416", "pid": "0x5302", "width": 320, "height": 240}
            Path(tmp, "device_info.yaml").write_text(yaml.safe_dump(info))
            det = _detector(tmp)
            with mock.patch("thermalright_lcd_control.device_controller.display."
                            "device_registry.list_devices", return_value=[]), \
                 mock.patch("usb.core.find", return_value=object()):
                self.assertEqual(det.get_devices(), [info])
            with mock.patch("thermalright_lcd_control.device_controller.display."
                            "device_registry.list_devices", return_value=[]), \
                 mock.patch("usb.core.find", return_value=None):
                self.assertEqual(det.get_devices(), [])

    def test_no_config_at_all_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            det = _detector(tmp)
            with mock.patch("thermalright_lcd_control.device_controller.display."
                            "device_registry.list_devices", return_value=[]):
                self.assertEqual(det.get_devices(), [])


if __name__ == "__main__":
    unittest.main()
