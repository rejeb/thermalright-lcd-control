# SPDX-License-Identifier: Apache-2.0
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app():
    return QApplication.instance() or QApplication([])


class TestResolutionCheck(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, tmp):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        cfg = {"paths": {"backgrounds_dir": str(tmp)}, "supported_formats": {}}
        return AppBackend(cfg, [], event_bus=None, controller=mock.MagicMock())

    def test_supported_when_folder_exists(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "320240").mkdir()
            be = self._backend(tmp)
            self.assertTrue(be._resolution_supported(320, 240))
            self.assertEqual(json.loads(be.check_resolution("320", "240")),
                             {"supported": True})

    def test_unsupported_when_folder_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            be = self._backend(tmp)
            self.assertFalse(be._resolution_supported(640, 480))
            self.assertEqual(json.loads(be.check_resolution("640", "480")),
                             {"supported": False})

    def test_invalid_input_is_unsupported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            be = self._backend(tmp)
            self.assertFalse(be._resolution_supported("", ""))
            self.assertFalse(be._resolution_supported(0, 240))

    def test_add_device_rejects_unsupported_resolution(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            be = self._backend(tmp)
            res = json.loads(be.add_device(json.dumps(
                {"width": 640, "height": 480, "vid": "0x0416", "pid": "0x5302"})))
            self.assertFalse(res["success"])
            self.assertIn("Unsupported resolution", res["error"])


class TestRotationMediaDirs(unittest.TestCase):
    def setUp(self):
        _app()

    def test_dirs_swap_on_rotation(self):
        import tempfile
        from pathlib import Path

        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        with tempfile.TemporaryDirectory() as tmp:
            for d in ("320240", "240320"):
                (Path(tmp) / d).mkdir()
            cfg = {"paths": {"backgrounds_dir": str(tmp),
                             "foregrounds_dir": str(tmp)},
                   "supported_formats": {}}
            be = AppBackend(cfg, [{"width": 320, "height": 240}],
                            event_bus=None, controller=mock.MagicMock())
            self.assertTrue(be.backgrounds_dir.endswith("320240"))
            self.assertTrue(str(be.foregrounds_dir).endswith("320240"))
            reloaded = []
            be.device_changed.connect(lambda: reloaded.append(True))
            be.set_rotation(90)
            self.assertTrue(be.backgrounds_dir.endswith("240320"))
            self.assertTrue(str(be.foregrounds_dir).endswith("240320"))
            self.assertTrue(str(be.themes_dir).endswith("240320"))
            # rotation = changement de device : l'UI recharge thèmes + médias
            self.assertEqual(reloaded, [True])
            # dimensions orientées côté preview
            self.assertEqual(json.loads(be.get_device_info())["width"], 240)
            be.set_rotation(180)
            self.assertTrue(be.backgrounds_dir.endswith("320240"))
            be.set_rotation(270)
            self.assertTrue(be.backgrounds_dir.endswith("240320"))


if __name__ == "__main__":
    unittest.main()
