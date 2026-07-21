import os
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display import font_manager


class TestFontManager(unittest.TestCase):
    def setUp(self):
        # fresh instance each test (avoid the process-global cache)
        self.fm = font_manager.SystemFontManager()

    def test_default_get_font_unchanged(self):
        # No style args → uses the existing default path, returns a usable font.
        font = self.fm.get_font(24)
        self.assertIsNotNone(font)

    def test_bold_and_regular_resolve_to_different_files(self):
        reg = self.fm.resolve_font_path("DejaVu Sans", bold=False, italic=False)
        bold = self.fm.resolve_font_path("DejaVu Sans", bold=True, italic=False)
        self.assertNotEqual(reg, bold)

    def test_fontconfig_failure_falls_back_to_bundled(self):
        with mock.patch.object(font_manager, "_fc_match", side_effect=RuntimeError("no fc")):
            path = self.fm.resolve_font_path("DejaVu Sans", bold=True, italic=False)
        self.assertIn("DejaVuSans-Bold", os.path.basename(path))

    def test_list_families_nonempty(self):
        fams = font_manager.list_font_families()
        self.assertTrue(fams)
        self.assertEqual(fams, sorted(fams))

    def test_list_families_fallback_when_fc_missing(self):
        with mock.patch.object(font_manager, "_fc_list", side_effect=RuntimeError("no fc")):
            fams = font_manager.list_font_families()
        self.assertIn("DejaVu Sans", fams)

    def test_fc_list_filters_symbol_and_icon_fonts(self):
        fake = ("FontAwesome\n"
                "DejaVu Sans,DejaVu Sans Bold\n"
                "Noto Color Emoji\n"
                "Material Icons\n"
                "Some Dingbats\n"
                "Liberation Serif\n")
        with mock.patch.object(font_manager.subprocess, "check_output", return_value=fake):
            fams = font_manager._fc_list()
        self.assertIn("DejaVu Sans", fams)
        self.assertIn("Liberation Serif", fams)
        for bad in ("FontAwesome", "Noto Color Emoji", "Material Icons", "Some Dingbats"):
            self.assertNotIn(bad, fams)


if __name__ == "__main__":
    unittest.main()
