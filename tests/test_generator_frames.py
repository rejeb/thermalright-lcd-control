# SPDX-License-Identifier: Apache-2.0
import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import BackgroundType
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator


def _decode(data: bytes) -> pyvips.Image:
    return vu.from_jpeg(data)


class Cfg:
    def __init__(self, tmp_path, fg=None):
        bg = tmp_path / "bg.png"
        vu.to_rgb(vu.solid(32, 24, (0, 0, 0, 255))).write_to_file(str(bg))
        self.background_path = str(bg)
        self.background_type = BackgroundType.IMAGE
        self.foreground_image_path = fg
        self.foreground_position = (0, 0)
        self.foreground_alpha = 1.0
        self.output_width, self.output_height = 32, 24
        self.rotation = 0
        self.metrics_configs = []
        self.date_config = None
        self.time_config = None
        self.global_font_path = None


def test_foreground_composited_into_cached_frames(tmp_path):
    fg = tmp_path / "fg.png"
    vu.solid(32, 24, (255, 0, 0, 255)).write_to_file(str(fg))
    gen = DisplayGenerator(Cfg(tmp_path, fg=str(fg)))
    base = gen.get_base_frame()
    assert isinstance(base, bytes)               # cache holds JPEG, not bitmaps
    r, g, b = vu.to_numpy(_decode(base))[5, 5]
    assert r > 240 and g < 15 and b < 15         # red fg (JPEG is lossy)
    gen.release()


def test_timing_owned_by_generator(tmp_path):
    gen = DisplayGenerator(Cfg(tmp_path))
    assert gen.frame_count == 1
    assert gen.peek_next_frame_idx() == 0
    gen.advance_frame_time()
    assert gen.frame_duration == 2.0
    gen.release()


def test_device_frame_is_decoded_image(tmp_path):
    gen = DisplayGenerator(Cfg(tmp_path))
    composed = gen.get_frame_with_metrics()
    assert isinstance(composed, pyvips.Image)
    assert composed.bands == 3
    gen.release()


def test_base_unrotated_device_frame_rotated(tmp_path):
    """Preview (base) frames stay unrotated; rotation is applied only on the
    device path, in compose_device_frame."""
    cfg = Cfg(tmp_path)
    cfg.rotation = 90
    gen = DisplayGenerator(cfg)
    base = _decode(gen.get_base_frame())
    assert (base.width, base.height) == (32, 24)            # unrotated preview
    dev = gen.get_frame_with_metrics()
    assert (dev.width, dev.height) == (24, 32)              # rotated for device
    gen.release()


def test_release_frees_frames(tmp_path):
    gen = DisplayGenerator(Cfg(tmp_path))
    gen.release()
    assert gen._frames == []
    assert gen._overlay is None and gen._foreground is None
