# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.controller import DeviceController

_MONITOR_PATH = "thermalright_lcd_control.device_controller.controller.DevicePresenceMonitor"


class TestDeviceController(unittest.TestCase):
    def _patched_loader(self, devices):
        loader = mock.MagicMock()
        loader.start_all.return_value = devices
        loader.active_engines.return_value = devices
        return loader

    def test_start_with_no_device_does_not_raise_and_marks_started(self):
        loader = self._patched_loader([])
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
            return_value=loader,
        ), mock.patch(_MONITOR_PATH):
            ctrl = DeviceController("/cfg")
            ctrl.start()  # must NOT raise / NOT exit even with no device
        loader.migrate_device_info.assert_called_once()
        loader.start_all.assert_called_once()
        self.assertTrue(ctrl.is_started)

    def test_start_is_idempotent(self):
        loader = self._patched_loader([object()])
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
            return_value=loader,
        ), mock.patch(_MONITOR_PATH):
            ctrl = DeviceController("/cfg")
            ctrl.start()
            ctrl.start()
        loader.start_all.assert_called_once()

    def test_start_starts_presence_monitor(self):
        loader = self._patched_loader([])
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
            return_value=loader,
        ), mock.patch(_MONITOR_PATH) as MonitorCls:
            ctrl = DeviceController("/cfg")
            ctrl.start()
        MonitorCls.assert_called_once_with("/cfg", ctrl, event_bus=None)
        MonitorCls.return_value.start.assert_called_once()

    def test_stop_calls_stop_all_and_is_idempotent(self):
        loader = self._patched_loader([object()])
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
            return_value=loader,
        ), mock.patch(_MONITOR_PATH) as MonitorCls:
            ctrl = DeviceController("/cfg")
            ctrl.start()
            ctrl.stop()
            ctrl.stop()
        loader.stop_all.assert_called_once()
        MonitorCls.return_value.stop.assert_called_once()
        self.assertFalse(ctrl.is_started)

    def test_event_bus_is_passed_to_loader(self):
        bus = object()
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
        ) as LoaderCls, mock.patch(_MONITOR_PATH):
            LoaderCls.return_value.start_all.return_value = []
            LoaderCls.return_value.active_engines.return_value = []
            ctrl = DeviceController("/cfg", event_bus=bus)
            ctrl.start()
        LoaderCls.assert_called_once_with("/cfg", event_bus=bus,
                                          active_device_id=None,
                                          media_active=True,
                                          media_endpoint=None)


class TestLoaderAttachesBus(unittest.TestCase):
    def test_started_engine_gets_event_bus_attached(self):
        import usb.core

        from thermalright_lcd_control.device_controller.display import device_loader as dl

        entry = {"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                 "width": 320, "height": 240, "generic": True}
        engine = mock.MagicMock()
        bus = object()
        loader = dl.DeviceLoader("/cfg", event_bus=bus)
        with mock.patch.object(loader, "load_entries", return_value=[entry]), \
             mock.patch.object(usb.core, "find", return_value=object()), \
             mock.patch.object(dl, "build_generic_device", return_value=mock.MagicMock()), \
             mock.patch.object(dl, "RenderEngine", return_value=engine), \
             mock.patch("threading.Thread"):
            loader.start_all()
        engine.attach_event_bus.assert_called_once_with(bus, "dev1")


class TestControllerRestart(unittest.TestCase):
    def test_restart_stops_then_starts_again(self):
        loader = mock.MagicMock()
        loader.start_all.return_value = [object()]
        loader.active_engines.return_value = [object()]
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
            return_value=loader,
        ), mock.patch(_MONITOR_PATH):
            ctrl = DeviceController("/cfg")
            ctrl.start()
            ctrl.restart()
        self.assertEqual(loader.start_all.call_count, 2)  # initial + restart
        loader.stop_all.assert_called_once()
        self.assertTrue(ctrl.is_started)

    def test_restart_when_not_started_just_starts(self):
        loader = mock.MagicMock()
        loader.start_all.return_value = []
        loader.active_engines.return_value = []
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
            return_value=loader,
        ), mock.patch(_MONITOR_PATH):
            ctrl = DeviceController("/cfg")
            ctrl.restart()
        loader.start_all.assert_called_once()
        self.assertTrue(ctrl.is_started)


class TestControllerBaseFrame(unittest.TestCase):
    def test_last_base_frame_reads_generator_singleton(self):
        from thermalright_lcd_control.device_controller.display import generator as gen_mod
        fake_gen = mock.MagicMock()
        fake_gen.current_base_frame.return_value = "FRAME"
        ctrl = DeviceController.__new__(DeviceController)
        with mock.patch.dict(gen_mod._instances, {"dev1": fake_gen}, clear=True):
            self.assertEqual(ctrl.last_base_frame("dev1"), "FRAME")
            self.assertIsNone(ctrl.last_base_frame("missing"))


class TestControllerTargetedMethods(unittest.TestCase):
    def _started_controller(self):
        loader = mock.MagicMock()
        loader.start_all.return_value = []
        loader.active_engines.return_value = []
        with mock.patch(
            "thermalright_lcd_control.device_controller.controller.DeviceLoader",
            return_value=loader,
        ), mock.patch(_MONITOR_PATH):
            ctrl = DeviceController("/cfg")
            ctrl.start()
        return ctrl, loader

    def test_add_device_engine_delegates_to_loader(self):
        ctrl, loader = self._started_controller()
        ctrl.add_device_engine("dev1")
        loader.start_one.assert_called_once_with("dev1")

    def test_remove_device_engine_delegates_to_loader(self):
        ctrl, loader = self._started_controller()
        ctrl.remove_device_engine("dev1")
        loader.stop_one.assert_called_once_with("dev1")

    def test_update_device_engine_stops_old_and_starts_new(self):
        ctrl, loader = self._started_controller()
        ctrl.update_device_engine("dev1", "dev1b")
        loader.stop_one.assert_called_once_with("dev1")
        loader.start_one.assert_called_once_with("dev1b")

    def test_targeted_methods_noop_before_start(self):
        ctrl = DeviceController("/cfg")
        ctrl.add_device_engine("dev1")      # must not raise
        ctrl.remove_device_engine("dev1")
        ctrl.update_device_engine("a", "b")

    def test_set_active_device_does_not_restart(self):
        ctrl, loader = self._started_controller()
        loader.start_all.reset_mock()
        loader.stop_all.reset_mock()
        ctrl.set_active_device("dev1")
        loader.start_all.assert_not_called()
        loader.stop_all.assert_not_called()
        self.assertEqual(ctrl.active_device_id, "dev1")

    def test_set_active_device_same_id_is_noop(self):
        ctrl, loader = self._started_controller()
        ctrl.active_device_id = "dev1"
        ctrl.set_active_device("dev1")
        loader.start_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
