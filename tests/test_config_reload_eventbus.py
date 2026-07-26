# SPDX-License-Identifier: Apache-2.0
"""Device-side handling of CONFIG_RELOAD events.

Devices no longer own a DisplayGenerator: rebuilding it is RenderEngine's job
(see tests/test_render_engine.py). A device only records that a reload was
requested for *its* id, together with any in-memory config that came with it.
"""
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
        dev.logger = mock.MagicMock()
        dev.config_file = "/cfg/config_dev1.yaml"
        return dev

    def test_matching_publish_sets_flag(self):
        dev = self._make_device()
        bus = EventBus()
        bus.subscribe(Topic.CONFIG_RELOAD, dev._on_config_reload)
        bus.publish(Topic.CONFIG_RELOAD, "dev1")
        self.assertTrue(dev._reload_requested.is_set())

    def test_matching_publish_keeps_the_inmemory_config(self):
        dev = self._make_device()
        bus = EventBus()
        bus.subscribe(Topic.CONFIG_RELOAD, dev._on_config_reload)
        bus.publish(Topic.CONFIG_RELOAD, "dev1", {"display": {"x": 1}})
        self.assertTrue(dev._reload_requested.is_set())
        self.assertEqual(dev._pending_config, {"display": {"x": 1}})

    def test_non_matching_publish_is_ignored(self):
        dev = self._make_device()
        dev._on_config_reload("other")
        self.assertFalse(dev._reload_requested.is_set())
        self.assertIsNone(dev._pending_config)


class TestLegacyReload(unittest.TestCase):
    def _make_device(self):
        from thermalright_lcd_control.device_controller.display import display_device as d

        class _Concrete(d.DisplayDevice):
            def get_header(self, *a, **k):
                return b""

            def send_packet(self, *a, **k):
                return None

        dev = _Concrete.__new__(_Concrete)
        dev._reload_requested = threading.Event()
        dev._pending_config = None
        dev._reload_id = "leg1"
        dev.logger = mock.MagicMock()
        dev.config_file = "/cfg/config_leg1.yaml"
        return dev

    def test_matching_publish_sets_flag(self):
        dev = self._make_device()
        dev._on_config_reload("leg1", {"display": {}})
        self.assertTrue(dev._reload_requested.is_set())
        self.assertEqual(dev._pending_config, {"display": {}})

    def test_non_matching_ignored(self):
        dev = self._make_device()
        dev._on_config_reload("nope")
        self.assertFalse(dev._reload_requested.is_set())
        self.assertIsNone(dev._pending_config)


if __name__ == "__main__":
    unittest.main()
