import os
import unittest

from thermalright_lcd_control.device_controller.display import bundled_fonts


class TestBundledFonts(unittest.TestCase):
    def test_dejavu_regular_file_exists(self):
        path = bundled_fonts.resolve("DejaVu Sans", bold=False, italic=False)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))

    def test_dejavu_bold_differs_from_regular(self):
        reg = bundled_fonts.resolve("DejaVu Sans", bold=False, italic=False)
        bold = bundled_fonts.resolve("DejaVu Sans", bold=True, italic=False)
        self.assertNotEqual(reg, bold)

    def test_alias_arial_maps_to_liberation_sans(self):
        path = bundled_fonts.resolve("Arial", bold=False, italic=False)
        self.assertIsNotNone(path)
        self.assertIn("LiberationSans", os.path.basename(path))

    def test_unknown_family_falls_back_to_dejavu(self):
        path = bundled_fonts.resolve("No Such Family 123", bold=True, italic=True)
        self.assertIn("DejaVuSans", os.path.basename(path))

    def test_families_lists_known_names(self):
        fams = bundled_fonts.families()
        self.assertIn("DejaVu Sans", fams)
        self.assertIn("Liberation Sans", fams)
        self.assertIn("Noto Sans", fams)


if __name__ == "__main__":
    unittest.main()
