# SPDX-License-Identifier: Apache-2.0
"""Add/edit device form: the resolution is picked from a closed list (parsed
from the backgrounds folders) instead of free-text width/height inputs."""
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _backend():
    from thermalright_lcd_control.gui.backend.app_backend import AppBackend
    cfg = {"paths": {"backgrounds_dir": "resources/themes/backgrounds"},
           "supported_formats": {}}
    return AppBackend(cfg, [], event_bus=None)


class TestDeviceDialogResolutionCombo(unittest.TestCase):
    def setUp(self):
        _app()
        self.backend = _backend()

    def test_combo_lists_parsed_resolutions(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend, edit_config={"id": "dev1"})
        expected = json.loads(self.backend.get_supported_resolutions())
        items = [dlg._res_combo.itemData(i) for i in range(dlg._res_combo.count())]
        self.assertEqual(items, [tuple(r) for r in expected])
        self.assertNotIn("width", dlg._inputs)      # no free-text inputs anymore
        self.assertNotIn("height", dlg._inputs)
        dlg.deleteLater()

    def test_edit_preselects_config_resolution(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend,
                           edit_config={"id": "dev1", "width": 1920, "height": 462})
        self.assertEqual(dlg._resolution(), (1920, 462))
        dlg.deleteLater()

    def test_edit_with_unknown_resolution_is_kept_but_flagged(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend,
                           edit_config={"id": "dev1", "width": 111, "height": 99})
        self.assertEqual(dlg._resolution(), (111, 99))
        self.assertFalse(dlg._check_resolution())   # no matching folder
        dlg.deleteLater()

    def test_submit_form_carries_selected_resolution(self):
        from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
        dlg = DeviceDialog(self.backend,
                           edit_config={"id": "dev1", "width": 320, "height": 240})
        captured = {}

        def fake_update(original_id, payload):
            captured.update(json.loads(payload))
            return json.dumps({"success": True})

        dlg.backend.update_device = fake_update
        dlg._submit()
        self.assertEqual((captured.get("width"), captured.get("height")),
                         ("320", "240"))
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
