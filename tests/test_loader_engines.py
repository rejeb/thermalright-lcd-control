# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest import mock

import usb.core


class TestLoaderBuildsEngines(unittest.TestCase):
    def _entry(self):
        return {"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                "width": 320, "height": 240, "generic": True}

    def test_present_device_engine_gets_sink_and_bus(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        bus = object()
        device = mock.MagicMock()
        engine = mock.MagicMock()
        loader = dl.DeviceLoader("/cfg", event_bus=bus)
        with mock.patch.object(loader, "load_entries", return_value=[self._entry()]), \
             mock.patch.object(usb.core, "find", return_value=object()), \
             mock.patch.object(dl, "build_generic_device", return_value=device) as bgd, \
             mock.patch.object(dl, "RenderEngine", return_value=engine) as RE, \
             mock.patch("threading.Thread"):
            engines = loader.start_all()
        bgd.assert_called_once()                       # device built as sink
        self.assertIn("build_generator", bgd.call_args.kwargs)
        self.assertEqual(bgd.call_args.kwargs["build_generator"], False)
        self.assertEqual(RE.call_args.kwargs.get("sink"), device)
        engine.attach_event_bus.assert_called_once_with(bus, "dev1")
        self.assertEqual(engines, [engine])

    def test_absent_active_device_gets_no_engine(self):
        """Superseded 'preview-only engine' behavior: an absent device never
        gets an engine, active or not (config editing without hardware no
        longer creates a live preview engine)."""
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        loader = dl.DeviceLoader("/cfg", active_device_id="dev1")
        with mock.patch.object(loader, "load_entries", return_value=[self._entry()]), \
             mock.patch.object(usb.core, "find", return_value=None), \
             mock.patch.object(dl, "RenderEngine") as RE, \
             mock.patch("threading.Thread"):
            engines = loader.start_all()
        RE.assert_not_called()
        self.assertEqual(engines, [])

    def test_absent_inactive_device_is_skipped(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        loader = dl.DeviceLoader("/cfg", active_device_id="other")
        with mock.patch.object(loader, "load_entries", return_value=[self._entry()]), \
             mock.patch.object(usb.core, "find", return_value=None), \
             mock.patch.object(dl, "RenderEngine") as RE, \
             mock.patch("threading.Thread"):
            engines = loader.start_all()
        RE.assert_not_called()            # absent + not active → no engine, no RAM
        self.assertEqual(engines, [])


class TestLoaderTargetedStartStop(unittest.TestCase):
    def _entry(self, id="dev1", vid=0x0416, pid=0x5302, width=320, height=240):
        return {"id": id, "vid": vid, "pid": pid, "width": width, "height": height,
                "generic": True}

    def test_start_one_builds_only_requested_device(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        entries = [self._entry(), self._entry(id="dev2", pid=0x5408, width=480, height=480)]
        engine = mock.MagicMock()
        loader = dl.DeviceLoader("/cfg")
        with mock.patch.object(loader, "load_entries", return_value=entries), \
             mock.patch.object(usb.core, "find", return_value=object()), \
             mock.patch.object(dl, "build_generic_device", return_value=mock.MagicMock()), \
             mock.patch.object(dl, "RenderEngine", return_value=engine), \
             mock.patch("threading.Thread"):
            result = loader.start_one("dev2")
        self.assertIs(result, engine)
        self.assertEqual(loader.active_engines(), [engine])  # only dev2, not dev1

    def test_start_one_absent_device_returns_none(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        loader = dl.DeviceLoader("/cfg")
        with mock.patch.object(loader, "load_entries", return_value=[self._entry()]), \
             mock.patch.object(usb.core, "find", return_value=None), \
             mock.patch.object(dl, "RenderEngine") as RE:
            result = loader.start_one("dev1")
        RE.assert_not_called()
        self.assertIsNone(result)

    def test_start_one_unknown_id_returns_none(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        loader = dl.DeviceLoader("/cfg")
        with mock.patch.object(loader, "load_entries", return_value=[self._entry()]):
            self.assertIsNone(loader.start_one("nope"))

    def test_start_one_is_idempotent(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        engine = mock.MagicMock()
        loader = dl.DeviceLoader("/cfg")
        with mock.patch.object(loader, "load_entries", return_value=[self._entry()]), \
             mock.patch.object(usb.core, "find", return_value=object()), \
             mock.patch.object(dl, "build_generic_device", return_value=mock.MagicMock()), \
             mock.patch.object(dl, "RenderEngine", return_value=engine) as RE, \
             mock.patch("threading.Thread"):
            loader.start_one("dev1")
            loader.start_one("dev1")            # second call must not rebuild
        RE.assert_called_once()

    def test_stop_one_closes_and_removes_only_that_engine(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        loader = dl.DeviceLoader("/cfg")
        engine1, thread1 = mock.MagicMock(), mock.MagicMock()
        engine2, thread2 = mock.MagicMock(), mock.MagicMock()
        loader._active = {"dev1": (engine1, thread1), "dev2": (engine2, thread2)}
        loader.stop_one("dev1")
        engine1.stop.assert_called_once()
        thread1.join.assert_called_once()
        engine1.close.assert_called_once()
        engine2.stop.assert_not_called()
        self.assertEqual(loader.active_engines(), [engine2])

    def test_stop_one_missing_device_is_noop(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        loader = dl.DeviceLoader("/cfg")
        loader.stop_one("nope")     # must not raise

    def test_stop_all_stops_every_active_device(self):
        from thermalright_lcd_control.device_controller.display import device_loader as dl
        loader = dl.DeviceLoader("/cfg")
        engine1, thread1 = mock.MagicMock(), mock.MagicMock()
        engine2, thread2 = mock.MagicMock(), mock.MagicMock()
        loader._active = {"dev1": (engine1, thread1), "dev2": (engine2, thread2)}
        loader.stop_all()
        engine1.stop.assert_called_once()
        engine2.stop.assert_called_once()
        self.assertEqual(loader.active_engines(), [])


if __name__ == "__main__":
    unittest.main()
