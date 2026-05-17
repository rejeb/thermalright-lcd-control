# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication


def _app():
    return QApplication.instance() or QApplication([])


class TestCloseToTray(unittest.TestCase):
    def setUp(self):
        _app()
        from thermalright_lcd_control.gui.native.main_window import NativeMainWindow
        fake = {"vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240, "id": "t"}
        self.win = NativeMainWindow("resources/gui_config.yaml", [fake])

    def tearDown(self):
        self.win._really_quit = True
        self.win.close()

    def test_close_hides_to_tray_by_default(self):
        self.win.show()
        ev = QCloseEvent()
        self.win.closeEvent(ev)
        self.assertFalse(ev.isAccepted())   # event ignored → not quitting
        self.assertTrue(self.win.isHidden())

    def test_close_accepts_when_really_quit(self):
        self.win.show()
        self.win._really_quit = True
        ev = QCloseEvent()
        self.win.closeEvent(ev)
        self.assertTrue(ev.isAccepted())

    def test_quit_app_requests_application_quit(self):
        with mock.patch.object(QApplication, "quit") as q:
            self.win._quit_app()
        q.assert_called_once()
        self.assertTrue(self.win._really_quit)


if __name__ == "__main__":
    unittest.main()
