# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.display import vips_utils as vu


def _app():
    return QApplication.instance() or QApplication([])


class TestPreviewSource(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, controller):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}],
                          event_bus=None, controller=controller)

    def test_tick_emits_frame_from_controller_base(self):
        controller = mock.MagicMock()
        controller.last_base_frame.return_value = vu.jpeg_bytes(vu.to_rgb(vu.solid(8, 4, (1, 2, 3, 255))))
        be = self._backend(controller)
        emitted = []
        be.frame_ready_pil.connect(emitted.append)
        be._tick()
        controller.last_base_frame.assert_called_with("dev1")
        self.assertTrue(emitted)
        img = vu.from_jpeg(emitted[0])
        self.assertEqual((img.width, img.height), (8, 4))

    def test_tick_no_base_frame_emits_nothing(self):
        controller = mock.MagicMock()
        controller.last_base_frame.return_value = None
        be = self._backend(controller)
        emitted = []
        be.frame_ready_pil.connect(emitted.append)
        be._tick()
        self.assertEqual(emitted, [])

    def test_tick_skips_reemit_when_base_unchanged(self):
        same = vu.jpeg_bytes(vu.to_rgb(vu.solid(8, 4, (1, 2, 3, 255))))
        controller = mock.MagicMock()
        controller.last_base_frame.return_value = same    # same object every tick
        be = self._backend(controller)
        emitted = []
        be.frame_ready_pil.connect(emitted.append)
        be._tick()
        be._tick()
        self.assertEqual(len(emitted), 1)                 # second tick is a no-op

    def test_tick_reemits_when_base_changes(self):
        controller = mock.MagicMock()
        be = self._backend(controller)
        emitted = []
        be.frame_ready_pil.connect(emitted.append)
        controller.last_base_frame.return_value = vu.jpeg_bytes(vu.to_rgb(vu.solid(8, 4, (1, 2, 3, 255))))
        be._tick()
        controller.last_base_frame.return_value = vu.jpeg_bytes(vu.to_rgb(vu.solid(8, 4, (9, 9, 9, 255))))
        be._tick()
        self.assertEqual(len(emitted), 2)


if __name__ == "__main__":
    unittest.main()
