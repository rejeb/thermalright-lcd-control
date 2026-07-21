# SPDX-License-Identifier: Apache-2.0
"""Device tabs in the titlebar: same selection rules as the old combobox,
edit (✎) button on the ACTIVE tab only."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabBar

from thermalright_lcd_control.gui.native.titlebar import TitleBar


def _app():
    return QApplication.instance() or QApplication([])


def _backend(devices):
    be = mock.MagicMock()
    be.config = {"paths": {}}
    be.get_devices.return_value = json.dumps(devices)
    be.get_ui_theme.return_value = "dark"
    return be


DEVS = [
    {"key": "0416:5302", "label": "Dev A", "id": "dev1", "current": False},
    {"key": "0416:5408", "label": "Dev B", "id": "dev2", "current": True},
]


class TestDeviceTabs(unittest.TestCase):
    def setUp(self):
        _app()

    def _bar(self, devices=DEVS):
        return TitleBar(_backend(devices))

    def test_tabs_populated_and_current_selected_without_select(self):
        bar = self._bar()
        self.assertEqual(bar.device_tabs.count(), 2)
        self.assertEqual(bar.device_tabs.tabText(0), "Dev A")
        self.assertEqual(bar.device_tabs.currentIndex(), 1)   # current flag
        bar.backend.select_device.assert_not_called()          # reload is silent
        self.assertEqual(bar.current_device_key(), "0416:5408")
        self.assertEqual(bar.current_device_id(), "dev2")

    def test_tab_click_selects_device(self):
        bar = self._bar()
        bar.device_tabs.setCurrentIndex(0)
        bar.backend.select_device.assert_called_once_with("0416:5302")

    def test_edit_button_follows_active_tab(self):
        bar = self._bar()
        tabs = bar.device_tabs
        self.assertIs(tabs.tabButton(1, QTabBar.RightSide), bar._tab_btns)
        self.assertIsNone(tabs.tabButton(0, QTabBar.RightSide))
        tabs.setCurrentIndex(0)
        self.assertIs(tabs.tabButton(0, QTabBar.RightSide), bar._tab_btns)
        self.assertIsNone(tabs.tabButton(1, QTabBar.RightSide))

    def test_edit_button_emits_edit_requested(self):
        bar = self._bar()
        hits = []
        bar.edit_device_requested.connect(lambda: hits.append(1))
        bar._tab_edit_btn.click()
        self.assertEqual(hits, [1])

    def test_delete_button_emits_delete_requested(self):
        bar = self._bar()
        hits = []
        bar.delete_device_requested.connect(lambda: hits.append(1))
        bar._tab_del_btn.click()
        self.assertEqual(hits, [1])

    def test_placeholder_when_no_devices(self):
        bar = self._bar(devices=[])
        tabs = bar.device_tabs
        self.assertEqual(tabs.count(), 1)
        self.assertEqual(tabs.tabText(0), "—")
        self.assertFalse(tabs.isTabEnabled(0))
        self.assertIsNone(tabs.tabButton(0, QTabBar.RightSide))   # no ✎
        self.assertIsNone(bar.current_device_key())
        bar.backend.select_device.assert_not_called()

    def test_reload_devices_is_idempotent(self):
        bar = self._bar()
        bar.reload_devices()
        bar.reload_devices()
        self.assertEqual(bar.device_tabs.count(), 2)
        self.assertEqual(bar.device_tabs.currentIndex(), 1)
        bar.backend.select_device.assert_not_called()


if __name__ == "__main__":
    unittest.main()
