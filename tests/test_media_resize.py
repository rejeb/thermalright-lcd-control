import subprocess
import tempfile
import unittest
from pathlib import Path

import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.gui.components import media_resize as mr


def _make_video(path: Path, seconds: float, fps: int = 10, size="64x48"):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"testsrc=duration={seconds}:size={size}:rate={fps}",
         "-pix_fmt", "yuv420p", str(path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class TestResizeImage(unittest.TestCase):
    def test_image_resized(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.png"
            vu.to_rgb(vu.solid(100, 50, (255, 0, 0, 255))).write_to_file(str(src))
            dst = Path(d) / "out.png"
            mr.resize_image(src, dst, 320, 240)
            img = pyvips.Image.new_from_file(str(dst))
            self.assertEqual((img.width, img.height), (320, 240))


class TestResizeGif(unittest.TestCase):
    def test_gif_resized_keeps_frames(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.gif"
            f1 = vu.to_rgb(vu.solid(40, 30, (255, 0, 0, 255)))
            f2 = vu.to_rgb(vu.solid(40, 30, (0, 0, 255, 255)))
            anim = f1.join(f2, "vertical").copy()
            anim.set_type(pyvips.GValue.gint_type, "page-height", 30)
            anim.set_type(pyvips.GValue.array_int_type, "delay", [100, 100])
            anim.write_to_file(str(src))
            dst = Path(d) / "out.gif"
            mr.resize_gif(src, dst, 320, 240)
            out = pyvips.Image.new_from_file(str(dst), n=-1)
            page_h = out.get("page-height")
            self.assertEqual((out.width, page_h), (320, 240))
            self.assertEqual(out.height // page_h, 2)


class TestResizeVideo(unittest.TestCase):
    def test_video_over_limit_rejected_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "long.mp4"; _make_video(src, 6.0)
            dst = Path(d) / "out.mp4"
            with self.assertRaises(mr.MediaTooLongError):
                mr.resize_video(src, dst, 320, 240)
            self.assertFalse(dst.exists())

    def test_video_under_limit_resized_keeps_fps(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.mp4"; _make_video(src, 2.0, fps=10, size="100x50")
            dst = Path(d) / "out.mp4"
            mr.resize_video(src, dst, 320, 240)
            self.assertTrue(dst.exists())
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,avg_frame_rate",
                 "-of", "csv=p=0", str(dst)],
                capture_output=True, text=True).stdout.strip()
            w, h, rate = probe.split(",")
            self.assertEqual((int(w), int(h)), (320, 240))
            num, den = rate.split("/")
            self.assertAlmostEqual(int(num) / int(den), 10, delta=1)


class TestMaterializeDispatch(unittest.TestCase):
    def test_image_keeps_ext(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.png"
            vu.to_rgb(vu.solid(10, 10, (0, 0, 0, 255))).write_to_file(str(src))
            out = mr.materialize(src, Path(d) / "dest", 320, 240)
            self.assertEqual(out.suffix, ".png")
            img = pyvips.Image.new_from_file(str(out))
            self.assertEqual((img.width, img.height), (320, 240))

    def test_video_becomes_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.avi"; _make_video(src, 1.0)
            out = mr.materialize(src, Path(d) / "dest", 320, 240)
            self.assertEqual(out.suffix, ".mp4")
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
