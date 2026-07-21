# SPDX-License-Identifier: Apache-2.0
"""The preview must render text at the SAME size the device renders it.

The device text renderer applies no upper font cap, so a config imported from a
large device (e.g. font_size 128 on a 462x1920 panel) must preview at its true
size — clamping the display font to the editing bound (FONT_MAX) made the
preview text smaller than the device.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.gui.native.overlay import model  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_widget_font_renders_true_size_above_editing_bound():
    _app()
    f = model.widget_font({"font_size": 128})
    assert f.pixelSize() == 128            # not shrunk to FONT_MAX


def test_widget_font_floors_tiny_or_invalid():
    _app()
    assert model.widget_font({"font_size": 2}).pixelSize() == model.FONT_MIN
    assert model.widget_font({"font_size": None}).pixelSize() >= model.FONT_MIN


def test_editing_bound_covers_imported_device_fonts():
    # the spinbox / resize bound must be able to represent device fonts (<=128
    # in the imported themes) rather than snapping them down.
    assert model.clamp_font(128) == 128
