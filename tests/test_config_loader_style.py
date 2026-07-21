import unittest
from unittest.mock import patch

from thermalright_lcd_control.device_controller.display.config_loader import ConfigLoader


class TestConfigLoaderStyle(unittest.TestCase):
    def setUp(self):
        self.loader = ConfigLoader()

    def test_metric_style_parsed(self):
        data = {
            "name": "cpu_temperature", "color": "#FFFFFFFF", "font_size": 24,
            "position": {"x": 10, "y": 20},
            "font_family": "DejaVu Sans", "bold": True, "italic": False,
            "label": "CPU", "label_position": {"x": 30, "y": 40},
            "label_font_family": "Noto Sans", "label_bold": False, "label_italic": True,
        }
        m = self.loader._parse_metric_config(data)
        self.assertEqual(m.font_family, "DejaVu Sans")
        self.assertTrue(m.bold)
        self.assertFalse(m.italic)
        self.assertEqual(m.label_font_family, "Noto Sans")
        self.assertFalse(m.label_bold)
        self.assertTrue(m.label_italic)

    def test_metric_style_defaults_when_absent(self):
        data = {"name": "cpu_temperature", "color": "#FFFFFFFF", "font_size": 24,
                "position": {"x": 10, "y": 20}}
        m = self.loader._parse_metric_config(data)
        self.assertIsNone(m.font_family)
        self.assertFalse(m.bold)
        self.assertFalse(m.italic)
        self.assertIsNone(m.label_font_family)
        self.assertFalse(m.label_bold)
        self.assertFalse(m.label_italic)

    def test_label_floating_parsed_and_defaults(self):
        on = self.loader._parse_metric_config({
            "name": "cpu_temperature", "color": "#FFFFFFFF", "font_size": 24,
            "position": {"x": 10, "y": 20}, "label": "CPU",
            "label_position": {"x": 1, "y": 2}, "label_floating": True})
        self.assertTrue(on.label_floating)
        off = self.loader._parse_metric_config({
            "name": "cpu_temperature", "color": "#FFFFFFFF", "font_size": 24,
            "position": {"x": 10, "y": 20}})
        self.assertFalse(off.label_floating)

    def test_text_style_parsed_and_defaults(self):
        t = self.loader._parse_text_config(
            {"color": "#FFFFFFFF", "font_size": 20, "position": {"x": 1, "y": 2},
             "font_family": "Ubuntu", "bold": True, "italic": True})
        self.assertEqual(t.font_family, "Ubuntu")
        self.assertTrue(t.bold)
        self.assertTrue(t.italic)
        t2 = self.loader._parse_text_config(
            {"color": "#FFFFFFFF", "font_size": 20, "position": {"x": 1, "y": 2}})
        self.assertIsNone(t2.font_family)
        self.assertFalse(t2.bold)
        self.assertFalse(t2.italic)

    def test_resolve_resolution_no_swap_for_0_and_180(self):
        self.assertEqual(self.loader.resolve_resolution_for_rotation(320, 240, 0), (320, 240))
        self.assertEqual(self.loader.resolve_resolution_for_rotation(320, 240, 180), (320, 240))

    def test_resolve_resolution_swaps_for_90_and_270(self):
        self.assertEqual(self.loader.resolve_resolution_for_rotation(320, 240, 90), (240, 320))
        self.assertEqual(self.loader.resolve_resolution_for_rotation(320, 240, 270), (240, 320))

    def test_load_config_from_dict_swaps_output_dims_and_resolution_for_90(self):
        yaml_data = {"display": {
            "rotation": 90,
            "background": {"path": "/base/{resolution}/bg.mp4", "type": "video"},
            "foreground": {"enabled": True, "path": "/base/{resolution}/fg.png",
                           "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
        }}
        cfg = self.loader.load_config_from_dict(yaml_data, 320, 240)
        self.assertEqual((cfg.output_width, cfg.output_height), (240, 320))
        self.assertEqual(cfg.background_path, "/base/240320/bg.mp4")
        self.assertEqual(cfg.foreground_image_path, "/base/240320/fg.png")

    def test_load_config_from_dict_no_swap_for_0(self):
        yaml_data = {"display": {
            "rotation": 0,
            "background": {"path": "/base/{resolution}/bg.mp4", "type": "video"},
            "foreground": {"enabled": False, "path": "", "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
        }}
        cfg = self.loader.load_config_from_dict(yaml_data, 320, 240)
        self.assertEqual((cfg.output_width, cfg.output_height), (320, 240))
        self.assertEqual(cfg.background_path, "/base/320240/bg.mp4")

    def test_media_endpoint_defaults_on_config(self):
        # config_loader no longer downloads; it stores the endpoint on the
        # config so FrameManager can fetch lazily at read time.
        yaml_data = {"display": {
            "rotation": 90,
            "background": {"path": "/base/{resolution}/a001.mp4", "type": "video"},
            "foreground": {"enabled": False, "path": "", "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
        }}
        cfg = self.loader.load_config_from_dict(yaml_data, 320, 240)
        self.assertEqual(cfg.background_path, "/base/240320/a001.mp4")
        self.assertEqual(cfg.media_endpoint, "https://api.thermalright.com/")

    def test_rotation_override_takes_precedence_over_file_rotation(self):
        # The theme file's own rotation may be stale (not saved yet) mid-edit;
        # a caller that already knows the intended rotation (e.g. a rotation
        # click reloading the active config before Save) must be able to force
        # it, so background/foreground paths resolve to the correct folder.
        yaml_data = {"display": {
            "rotation": 0,
            "background": {"path": "/base/{resolution}/bg.mp4", "type": "video"},
            "foreground": {"enabled": True, "path": "/base/{resolution}/fg.png",
                           "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
        }}
        cfg = self.loader.load_config_from_dict(yaml_data, 320, 240, rotation_override=90)
        self.assertEqual(cfg.rotation, 90)
        self.assertEqual((cfg.output_width, cfg.output_height), (240, 320))
        self.assertEqual(cfg.background_path, "/base/240320/bg.mp4")
        self.assertEqual(cfg.foreground_image_path, "/base/240320/fg.png")

    def test_no_rotation_override_uses_file_rotation(self):
        yaml_data = {"display": {
            "rotation": 90,
            "background": {"path": "/base/{resolution}/bg.mp4", "type": "video"},
            "foreground": {"enabled": False, "path": "", "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
        }}
        cfg = self.loader.load_config_from_dict(yaml_data, 320, 240)
        self.assertEqual(cfg.rotation, 90)
        self.assertEqual(cfg.background_path, "/base/240320/bg.mp4")

    def test_resolving_config_never_downloads(self):
        # config_loader must not perform network I/O — resolving a config for
        # listing/thumbnails only resolves paths; FrameManager owns downloads.
        yaml_data = {"display": {
            "rotation": 0,
            "background": {"path": "/base/{resolution}/a001.mp4", "type": "video"},
            "foreground": {"enabled": False, "path": "", "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
        }}
        with patch(
            "thermalright_lcd_control.device_controller.display.asset_download."
            "download_bundled_background"
        ) as mock_dl:
            self.loader.load_config_from_dict(yaml_data, 320, 240)
            mock_dl.assert_not_called()

    def test_media_endpoint_is_stored_on_config(self):
        yaml_data = {"display": {
            "rotation": 0,
            "background": {"path": "/base/{resolution}/a001.mp4", "type": "video"},
            "foreground": {"enabled": False, "path": "", "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
        }}
        cfg = self.loader.load_config_from_dict(
            yaml_data, 320, 240, media_endpoint="https://example.test/tr/")
        self.assertEqual(cfg.background_path, "/base/320240/a001.mp4")
        self.assertEqual(cfg.media_endpoint, "https://example.test/tr/")


if __name__ == "__main__":
    unittest.main()
