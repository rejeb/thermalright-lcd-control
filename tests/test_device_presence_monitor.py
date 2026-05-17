# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display.device_presence_monitor import (
    DevicePresenceMonitor,
)
from thermalright_lcd_control.device_controller.display.event_bus import Topic


class TestPollOnce(unittest.TestCase):
    def _monitor(self, present_sequence, list_devices_return=None):
        controller = mock.MagicMock()
        event_bus = mock.MagicMock()
        mon = DevicePresenceMonitor("/cfg", controller, event_bus=event_bus)
        patcher = mock.patch(
            "thermalright_lcd_control.device_controller.display."
            "device_presence_monitor.device_registry.present_device_ids",
            side_effect=present_sequence)
        patcher.start()
        self.addCleanup(patcher.stop)
        if list_devices_return is not None:
            lp = mock.patch(
                "thermalright_lcd_control.device_controller.display."
                "device_presence_monitor.device_registry.list_devices",
                return_value=list_devices_return)
            lp.start()
            self.addCleanup(lp.stop)
        return mon, controller, event_bus

    def test_no_change_does_nothing(self):
        mon, controller, event_bus = self._monitor([{"dev1"}, {"dev1"}])
        mon.start = lambda: None  # not exercising the thread here
        mon._present = {"dev1"}
        mon.poll_once()
        controller.add_device_engine.assert_not_called()
        controller.remove_device_engine.assert_not_called()
        event_bus.publish.assert_not_called()

    def test_disappeared_device_is_removed_and_published(self):
        entries = [{"id": "dev2", "vid": 1, "pid": 2, "width": 1, "height": 1}]
        mon, controller, event_bus = self._monitor([{"dev2"}], list_devices_return=entries)
        mon._present = {"dev1", "dev2"}
        mon.poll_once()
        controller.remove_device_engine.assert_called_once_with("dev1")
        controller.add_device_engine.assert_not_called()
        event_bus.publish.assert_called_once_with(Topic.DEVICES_CHANGED, entries)
        self.assertEqual(mon._present, {"dev2"})

    def test_appeared_device_is_added_and_published(self):
        entries = [{"id": "dev1", "vid": 1, "pid": 2, "width": 1, "height": 1}]
        mon, controller, event_bus = self._monitor([{"dev1"}], list_devices_return=entries)
        mon._present = set()
        mon.poll_once()
        controller.add_device_engine.assert_called_once_with("dev1")
        controller.remove_device_engine.assert_not_called()
        event_bus.publish.assert_called_once_with(Topic.DEVICES_CHANGED, entries)

    def test_publish_list_is_filtered_to_present_only(self):
        all_entries = [{"id": "dev1", "vid": 1, "pid": 2, "width": 1, "height": 1},
                       {"id": "dev2", "vid": 3, "pid": 4, "width": 1, "height": 1}]
        mon, controller, event_bus = self._monitor([{"dev1"}], list_devices_return=all_entries)
        mon._present = set()
        mon.poll_once()
        published = event_bus.publish.call_args.args[1]
        self.assertEqual([e["id"] for e in published], ["dev1"])

    def test_no_event_bus_does_not_crash(self):
        controller = mock.MagicMock()
        mon = DevicePresenceMonitor("/cfg", controller, event_bus=None)
        with mock.patch(
            "thermalright_lcd_control.device_controller.display."
            "device_presence_monitor.device_registry.present_device_ids",
            return_value={"dev1"}), \
            mock.patch(
            "thermalright_lcd_control.device_controller.display."
            "device_presence_monitor.device_registry.list_devices",
            return_value=[{"id": "dev1", "vid": 1, "pid": 2, "width": 1, "height": 1}]):
            mon._present = set()
            mon.poll_once()   # must not raise
        controller.add_device_engine.assert_called_once_with("dev1")


class TestStartStopLifecycle(unittest.TestCase):
    def test_start_seeds_present_set_and_spawns_thread(self):
        controller = mock.MagicMock()
        with mock.patch(
            "thermalright_lcd_control.device_controller.display."
            "device_presence_monitor.device_registry.present_device_ids",
            return_value={"dev1"}):
            mon = DevicePresenceMonitor("/cfg", controller, interval=0.01)
            mon.start()
            thread = mon._thread
            try:
                self.assertEqual(mon._present, {"dev1"})
                self.assertTrue(thread.is_alive())
            finally:
                mon.stop()
        self.assertFalse(thread.is_alive())
        self.assertIsNone(mon._thread)

    def test_stop_before_start_does_not_raise(self):
        mon = DevicePresenceMonitor("/cfg", mock.MagicMock())
        mon.stop()   # must not raise


if __name__ == "__main__":
    unittest.main()
