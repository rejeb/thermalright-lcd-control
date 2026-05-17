# SPDX-License-Identifier: Apache-2.0
"""Device switch must NOT auto-save the outgoing device's config: the user
decides when to save (Save button). Switching simply drops unsaved edits."""
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

DEV1 = {"id": "dev1", "vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240}
DEV2 = {"id": "dev2", "vid": 0x0416, "pid": 0x5408, "width": 1920, "height": 440}


def _app():
    return QApplication.instance() or QApplication([])


class TestSelectDeviceDoesNotSave(unittest.TestCase):
    def setUp(self):
        _app()
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {}, "supported_formats": {}}
        self.be = AppBackend(cfg, [DEV1, DEV2], event_bus=None,
                             controller=mock.MagicMock())

    def _key(self, d):
        return self.be._device_key(d)

    def test_switch_does_not_save_outgoing_config(self):
        with mock.patch.object(self.be, "apply") as apply_, \
             mock.patch.object(self.be, "_apply_device") as switch:
            self.be.select_device(self._key(DEV2))
        apply_.assert_not_called()                     # no auto-save on switch
        switch.assert_called_once()

    def test_reselect_active_device_is_a_noop(self):
        with mock.patch.object(self.be, "apply") as apply_, \
             mock.patch.object(self.be, "_apply_device") as switch:
            self.be.select_device(self._key(DEV1))     # already active
        apply_.assert_not_called()
        switch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
