# SPDX-License-Identifier: Apache-2.0
"""Regression test: the preview zone must resize (swap orientation) when the
user rotates the device 90°/270°.

Root cause under test: ``PreviewPanel.reload_device_info()`` already stores
*oriented* dims in ``device_w``/``device_h`` (via ``get_device_info()`` ->
``_media_res()``, which swaps for 90/270). ``MainWindow._update_responsive_layout``
used to swap them *again* based on ``self.preview.rotation``, cancelling the
effect and leaving the visible preview box in its original (unrotated) shape.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


class TestPreviewLayoutRotation(unittest.TestCase):
    def setUp(self):
        _app()
        from thermalright_lcd_control.gui.native.main_window import NativeMainWindow
        # Non-square device so a 90° swap actually changes the aspect ratio.
        # Use a device id not shared with any other test/real config fixture,
        # so this test's on-disk active config starts clean at rotation 0.
        fake = {"vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240,
                "id": "rotation_layout_test"}
        self.win = NativeMainWindow("resources/gui_config.yaml", [fake])
        self.win.resize(1200, 800)
        # Normalize: this device's active config may already exist with a
        # non-zero rotation from a previous run of this same test.
        self.win.backend.set_rotation(0)
        self.win.preview.reload_device_info()
        self.win.preview._set_rotation(0)
        self.win._update_responsive_layout()

    def tearDown(self):
        self.win._really_quit = True
        self.win.close()
        from pathlib import Path
        cfg = Path("resources/config/config_rotation_layout_test.yaml")
        if cfg.exists():
            cfg.unlink()

    def test_preview_box_swaps_aspect_ratio_after_90deg_rotation(self):
        view = self.win.preview.view
        landscape = view.width() > view.height()
        self.assertTrue(landscape, (view.width(), view.height()))

        self.win.preview._rot_buttons[90].click()  # user picks the 90° radio
        self.win._update_responsive_layout()

        portrait = view.height() > view.width()
        self.assertTrue(portrait, (view.width(), view.height()))


if __name__ == "__main__":
    unittest.main()
