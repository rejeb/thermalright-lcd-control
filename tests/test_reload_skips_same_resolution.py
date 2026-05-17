# SPDX-License-Identifier: Apache-2.0
import os
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


class _Tabs:
    def __init__(self):
        self.calls = []

    def load_themes(self, select_name=None):
        self.calls.append("themes")
        return []

    def load_backgrounds(self):
        self.calls.append("bg")

    def load_foregrounds(self):
        self.calls.append("fg")

    def load_all(self):
        self.load_themes()
        self.load_backgrounds()
        self.load_foregrounds()
        return []


def _make_window():
    from thermalright_lcd_control.gui.native.main_window import NativeMainWindow
    _app()
    win = NativeMainWindow.__new__(NativeMainWindow)   # bypass full Qt init
    win.tabs = _Tabs()
    win.backend = mock.MagicMock()
    # reload_for_device keys on the media resolution (rotation-swapped), so drive
    # the test through _media_res(), not the raw device dimensions.
    win.backend._media_res = mock.Mock(return_value=(320, 240))
    win.preview = mock.MagicMock()
    win.editor = mock.MagicMock()
    win._last_media_res = None
    return win


def test_first_load_loads_all_grids():
    win = _make_window()
    win.reload_for_device()
    assert win.tabs.calls == ["themes", "bg", "fg"]


def test_same_resolution_switch_skips_bg_and_fg():
    win = _make_window()
    win.reload_for_device()
    win.tabs.calls.clear()
    win.reload_for_device()                       # same 320x240
    assert win.tabs.calls == ["themes"]           # bg/fg skipped


def test_resolution_change_reloads_all():
    win = _make_window()
    win.reload_for_device()
    win.tabs.calls.clear()
    win.backend._media_res.return_value = (480, 480)
    win.reload_for_device()
    assert win.tabs.calls == ["themes", "bg", "fg"]


def test_rotation_reloads_all_grids():
    # A rotation swaps the media resolution (320x240 -> 240x320) even though the
    # device dimensions are unchanged; bg/fg grids must reload for the new folder.
    win = _make_window()
    win.reload_for_device()
    win.tabs.calls.clear()
    win.backend._media_res.return_value = (240, 320)   # rotated
    win.reload_for_device()
    assert win.tabs.calls == ["themes", "bg", "fg"]
