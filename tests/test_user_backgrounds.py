import tempfile
import unittest
from pathlib import Path

import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu

from thermalright_lcd_control.gui.components import user_backgrounds as ub


def _img(p: Path, size=(100, 50), color="red"):
    vu.to_rgb(vu.solid(*size, (*color, 255)) if isinstance(color, tuple) else vu.solid(*size, (255, 0, 0, 255))).write_to_file(str(p))


class TestImportOriginals(unittest.TestCase):
    def test_single_file_copied_unmodified(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); src = d / "photo.png"; _img(src, (100, 50))
            orig = ub.import_originals([src], d / "orig")
            self.assertTrue(orig.exists())
            self.assertTrue(orig.name.startswith("user_"))
            img = pyvips.Image.new_from_file(str(orig))
            self.assertEqual((img.width, img.height), (100, 50))   # NON redimensionné

    def test_multi_file_collection(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = d / "a.png"; b = d / "b.png"; _img(a); _img(b)
            orig = ub.import_originals([a, b], d / "orig")
            self.assertTrue(orig.is_dir())
            self.assertTrue(orig.name.startswith("collection_"))
            self.assertEqual(len(list(orig.glob("*.png"))), 2)


class TestMaterialize(unittest.TestCase):
    def test_materialize_for_creates_resized_copy(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); orig = d / "orig"; bg = d / "bg"
            src = d / "photo.png"; _img(src, (100, 50))
            o = ub.import_originals([src], orig)
            ub.materialize_for(orig, bg, 320, 240)
            copy = bg / "320240" / o.name
            self.assertTrue(copy.exists())
            img = pyvips.Image.new_from_file(str(copy))
            self.assertEqual((img.width, img.height), (320, 240))

    def test_materialize_for_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); orig = d / "orig"; bg = d / "bg"
            src = d / "photo.png"; _img(src)
            o = ub.import_originals([src], orig)
            ub.materialize_for(orig, bg, 320, 240)
            copy = bg / "320240" / o.name
            mtime = copy.stat().st_mtime_ns
            ub.materialize_for(orig, bg, 320, 240)               # 2e passe
            self.assertEqual(copy.stat().st_mtime_ns, mtime)     # non réécrit

    def test_materialize_all_covers_every_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); orig = d / "orig"; bg = d / "bg"
            src = d / "photo.png"; _img(src)
            o = ub.import_originals([src], orig)
            ub.materialize_all(orig, bg, [(320, 240), (480, 480)])
            self.assertTrue((bg / "320240" / o.name).exists())
            self.assertTrue((bg / "480480" / o.name).exists())


class TestDelete(unittest.TestCase):
    def test_delete_removes_original_and_all_copies(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); orig = d / "orig"; bg = d / "bg"
            src = d / "photo.png"; _img(src)
            o = ub.import_originals([src], orig)
            ub.materialize_all(orig, bg, [(320, 240), (480, 480)])
            ub.delete_user_background(o.name, orig, bg)
            self.assertFalse(o.exists())
            self.assertFalse((bg / "320240" / o.name).exists())
            self.assertFalse((bg / "480480" / o.name).exists())


class TestMigrate(unittest.TestCase):
    def test_legacy_copy_becomes_original_and_regenerated(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); orig = d / "orig"; bg = d / "bg"
            legacy = bg / "320240"; legacy.mkdir(parents=True)
            _img(legacy / "user_old.png", (100, 50))    # stocké non redimensionné
            ub.migrate_legacy(orig, bg, [(320, 240), (480, 480)])
            self.assertTrue((orig / "user_old.png").exists())          # original créé
            img = pyvips.Image.new_from_file(str(bg / "320240" / "user_old.png"))
            self.assertEqual((img.width, img.height), (320, 240))
            self.assertTrue((bg / "480480" / "user_old.png").exists()) # autre résolution

    def test_migrate_idempotent_when_original_exists(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); orig = d / "orig"; bg = d / "bg"
            orig.mkdir(parents=True); _img(orig / "user_x.png")
            (bg / "320240").mkdir(parents=True); _img(bg / "320240" / "user_x.png")
            before = (orig / "user_x.png").stat().st_mtime_ns
            ub.migrate_legacy(orig, bg, [(320, 240)])
            self.assertEqual((orig / "user_x.png").stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
