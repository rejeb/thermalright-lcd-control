# SPDX-License-Identifier: Apache-2.0
"""Regression test: the background path saved by ConfigGenerator must carry a
{resolution} placeholder (like the foreground path already does), so a later
device/rotation change can re-template it to the new resolution folder instead
of staying stuck at whatever resolution was active when the theme was saved.
"""
import unittest
from unittest.mock import MagicMock

from thermalright_lcd_control.gui.components.config_generator import ConfigGenerator


class TestBackgroundResolutionPlaceholder(unittest.TestCase):
    def setUp(self):
        self.gen = ConfigGenerator({"paths": {}})

    def _preview_manager(self, bg_path):
        pm = MagicMock()
        pm.current_background_path = bg_path
        pm.current_foreground_path = None
        pm.preview_width = 240
        pm.preview_height = 320
        pm.current_rotation = 90
        pm.foreground_opacity = 1.0
        pm.determine_background_type.return_value = MagicMock(value="video")
        return pm

    def _overlay_manager(self):
        om = MagicMock()
        om.to_display_config.return_value = {
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False}, "time": {"enabled": False}, "texts": [],
        }
        return om

    def test_background_path_gets_resolution_placeholder(self):
        pm = self._preview_manager("/base/240320/a001.mp4")
        data = self.gen.generate_config_data_from_overlays(pm, self._overlay_manager())
        self.assertEqual(data["display"]["background"]["path"], "/base/{resolution}/a001.mp4")

    def test_user_background_without_resolution_dir_is_left_untouched(self):
        pm = self._preview_manager("/base/user_backgrounds/user_foo.png")
        data = self.gen.generate_config_data_from_overlays(pm, self._overlay_manager())
        self.assertEqual(data["display"]["background"]["path"],
                         "/base/user_backgrounds/user_foo.png")


if __name__ == "__main__":
    unittest.main()
