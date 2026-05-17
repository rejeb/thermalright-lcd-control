# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.display.event_bus import EventBus, Topic


def _app():
    return QApplication.instance() or QApplication([])


class TestBackendPublishReload(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, bus):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        be = AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                               "width": 320, "height": 240}], event_bus=bus)
        be.config_gen = mock.MagicMock()
        be.config_gen.generate_config_yaml_from_overlays.return_value = "/tmp/config_dev1.yaml"
        return be

    def test_live_persist_publishes_for_active_device(self):
        bus = EventBus()
        received = []
        bus.subscribe(Topic.CONFIG_RELOAD, lambda device_id, config=None: received.append(device_id))
        be = self._backend(bus)
        be._persist(preview=True)
        self.assertEqual(received, ["dev1"])

    def test_save_does_not_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe(Topic.CONFIG_RELOAD, lambda device_id, config=None: received.append(device_id))
        be = self._backend(bus)
        be._persist(preview=False)   # save → theme snapshot, no live push
        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
