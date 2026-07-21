# SPDX-License-Identifier: Apache-2.0
"""Regression: a widget color stored as ``#RRGGBBAA`` (how configs persist it)
must render with the right channels in the preview. Qt's ``QColor`` parses an
8-hex-digit ``#`` string as ``#AARRGGBB``, so ``#FF0000FF`` (red) would come out
blue — the device path parses RGBA correctly, so preview and device diverged
after a reload."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from thermalright_lcd_control.gui.native.overlay.items import _qcolor  # noqa: E402


def test_rrggbbaa_is_not_channel_swapped():
    c = _qcolor("#FF0000FF")            # red, opaque, RRGGBBAA
    assert (c.red(), c.green(), c.blue(), c.alpha()) == (255, 0, 0, 255)


def test_rrggbbaa_honours_alpha():
    c = _qcolor("#00FF0080")            # green, half alpha
    assert (c.red(), c.green(), c.blue()) == (0, 255, 0)
    assert c.alpha() == 0x80


def test_plain_rrggbb():
    c = _qcolor("#0000FF")
    assert (c.red(), c.green(), c.blue()) == (0, 0, 255)


def test_none_defaults_to_white():
    c = _qcolor(None)
    assert (c.red(), c.green(), c.blue()) == (255, 255, 255)
