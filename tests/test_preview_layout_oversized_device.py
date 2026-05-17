# SPDX-License-Identifier: Apache-2.0
"""Regression test: a device whose resolution exceeds the window must yield a
preview scaled down to fit, not a fixed-size view larger than the window
(which gets truncated, with no scrolling).

Root cause under test: ``MainWindow._update_responsive_layout`` computed the
preview box with a *floor* of 75 % of the device's long side but no ceiling,
so ``set_target_box()`` fixed the view at e.g. 1440px inside a 1200px window.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


class TestPreviewLayoutOversizedDevice(unittest.TestCase):
    def setUp(self):
        _app()
        from thermalright_lcd_control.gui.native.main_window import NativeMainWindow
        fake = {"vid": 0x0416, "pid": 0x5302, "width": 1920, "height": 1080,
                "id": "oversized_layout_test"}
        self.win = NativeMainWindow("resources/gui_config.yaml", [fake])
        self.win.resize(1200, 800)
        self.win.preview.reload_device_info()
        self.win._update_responsive_layout()

    def tearDown(self):
        self.win._really_quit = True
        self.win.close()
        from pathlib import Path
        cfg = Path("resources/config/config_oversized_layout_test.yaml")
        if cfg.exists():
            cfg.unlink()

    def test_preview_fits_inside_window(self):
        view = self.win.preview.view
        self.assertLessEqual(view.width(), self.win.width(),
                             (view.width(), self.win.width()))
        self.assertLessEqual(view.height(), self.win.height(),
                             (view.height(), self.win.height()))
        # aspect ratio preserved (16:9)
        self.assertAlmostEqual(view.width() / view.height(), 1920 / 1080,
                               delta=0.05)


if __name__ == "__main__":
    unittest.main()
