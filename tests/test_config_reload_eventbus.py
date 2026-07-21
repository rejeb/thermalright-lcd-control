# SPDX-License-Identifier: Apache-2.0
import threading
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display.event_bus import EventBus, Topic


class TestGenericReload(unittest.TestCase):
    def _make_device(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = g.GenericDisplayDevice.__new__(g.GenericDisplayDevice)
        dev._reload_requested = threading.Event()
        dev._pending_config = None
        dev._reload_id = "dev1"
        dev._generator = mock.MagicMock(name="OLD")
        dev._build_generator = mock.MagicMock(return_value="NEW")
        dev.logger = mock.MagicMock()
        dev.config_file = "/cfg/config_dev1.yaml"
        return dev

    def test_matching_publish_sets_flag_and_rebuilds(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = self._make_device()
        bus = EventBus()
        bus.subscribe(Topic.CONFIG_RELOAD, dev._on_config_reload)
        bus.publish(Topic.CONFIG_RELOAD, "dev1")
        self.assertTrue(dev._reload_requested.is_set())
        old = dev._generator
        self.assertEqual(g.GenericDisplayDevice._get_generator(dev), "NEW")
        self.assertFalse(dev._reload_requested.is_set())
        old.release.assert_called_once()  # the discarded clip must be freed

    def test_non_matching_publish_is_ignored(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = self._make_device()
        dev._on_config_reload("other")
        self.assertFalse(dev._reload_requested.is_set())
        self.assertIs(g.GenericDisplayDevice._get_generator(dev), dev._generator)
        dev._build_generator.assert_not_called()


class TestLegacyReload(unittest.TestCase):
    def _concrete_cls(self):
        from thermalright_lcd_control.device_controller.display import display_device as d

        class _Concrete(d.DisplayDevice):
            def get_header(self, *a, **k):
                return b""

            def send_packet(self, *a, **k):
                return None

        return _Concrete

    def _make_device(self):
        cls = self._concrete_cls()
        dev = cls.__new__(cls)
        dev._reload_requested = threading.Event()
        dev._pending_config = None
        dev._reload_id = "leg1"
        dev._generator = mock.MagicMock(name="OLD")
        dev._build_generator = mock.MagicMock(return_value="NEW")
        dev.logger = mock.MagicMock()
        dev.config_file = "/cfg/config_leg1.yaml"
        return dev

    def test_matching_publish_rebuilds(self):
        from thermalright_lcd_control.device_controller.display import display_device as d
        dev = self._make_device()
        dev._on_config_reload("leg1")
        old = dev._generator
        self.assertEqual(d.DisplayDevice._get_generator(dev), "NEW")
        old.release.assert_called_once()  # the discarded clip must be freed

    def test_non_matching_ignored(self):
        from thermalright_lcd_control.device_controller.display import display_device as d
        dev = self._make_device()
        dev._on_config_reload("nope")
        self.assertIs(d.DisplayDevice._get_generator(dev), dev._generator)


if __name__ == "__main__":
    unittest.main()
