# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.display.event_bus import EventBus, Topic


def _app():
    return QApplication.instance() or QApplication([])


class TestLivePublish(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, bus):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        be = AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                               "width": 320, "height": 240}], event_bus=bus)
        be.config_gen = mock.MagicMock()
        be.config_gen.generate_config_data_from_overlays.return_value = {"display": {"k": 1}}
        return be

    def test_publish_live_emits_inmemory_config(self):
        bus = EventBus()
        received = []
        bus.subscribe(Topic.CONFIG_RELOAD,
                      lambda device_id, config=None: received.append((device_id, config)))
        be = self._backend(bus)
        be._publish_live()
        self.assertEqual(received, [("dev1", {"display": {"k": 1}})])

    def test_setters_push_config_to_engine(self):
        # set_rotation and set_foreground_opacity both push a live (unsaved)
        # config — neither writes a file — and both notify the engine via a
        # CONFIG_RELOAD so the device reflects the change.
        bus = EventBus()
        events = []
        bus.subscribe(Topic.CONFIG_RELOAD,
                      lambda device_id, config=None: events.append(device_id))
        be = self._backend(bus)
        be.set_rotation(180)            # live publish → engine reload
        be.set_foreground_opacity(0.7)  # live publish → engine reload
        self.assertGreaterEqual(len(events), 2)

    def test_rotation_does_not_persist_active_config(self):
        # Rotating updates the live preview only; it does not write the active
        # config to disk — the user persists explicitly via Apply/Save.
        bus = EventBus()
        be = self._backend(bus)
        be.apply = mock.MagicMock()
        be.set_rotation(90)
        be.apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
