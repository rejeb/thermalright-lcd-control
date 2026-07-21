# SPDX-License-Identifier: Apache-2.0
from thermalright_lcd_control.device_controller.display import vips_utils as vu

from thermalright_lcd_control.device_controller.display.config import BackgroundType
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator


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


def test_acquire_is_singleton_per_device(tmp_path):
    cfg = Cfg(tmp_path)
    a = DisplayGenerator.acquire("dev1", cfg)
    assert DisplayGenerator.acquire("dev1", cfg) is a
    assert DisplayGenerator.get("dev1") is a
    b = DisplayGenerator.acquire("dev2", cfg)
    assert b is not a
    DisplayGenerator.release_device("dev1")
    DisplayGenerator.release_device("dev2")


def test_replace_releases_previous(tmp_path):
    cfg = Cfg(tmp_path)
    old = DisplayGenerator.acquire("dev1", cfg)
    new = DisplayGenerator.replace("dev1", cfg)
    assert new is not old
    assert old._frames == []          # released → no leaked clip
    assert DisplayGenerator.get("dev1") is new
    DisplayGenerator.release_device("dev1")


def test_release_device_evicts(tmp_path):
    DisplayGenerator.acquire("dev1", Cfg(tmp_path))
    DisplayGenerator.release_device("dev1")
    assert DisplayGenerator.get("dev1") is None
    DisplayGenerator.release_device("dev1")   # idempotent
