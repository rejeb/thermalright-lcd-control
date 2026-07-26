# SPDX-License-Identifier: Apache-2.0
"""Theme thumbnails show a COMPOSITE preview (background + foreground + overlays),
not just the background, and regenerate when the theme file changes."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.device_controller.display import vips_utils as vu  # noqa: E402
from thermalright_lcd_control.gui.components import thumbnail_render as tr  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _theme_yaml(bg: Path, fg: Path) -> str:
    return f"""display:
  rotation: 0
  background: {{path: "{bg}", type: image}}
  foreground: {{enabled: true, path: "{fg}", position: {{x: 180, y: 120}}, alpha: 1.0}}
  metrics: {{enabled: false, configs: []}}
  date: {{enabled: false}}
  time: {{enabled: false}}
  texts: []
"""


class TestThemeCompositeThumbnail(unittest.TestCase):
    def setUp(self):
        _app()

    def _backend(self, d):
        from thermalright_lcd_control.gui.backend.app_backend import AppBackend
        self.pr = Path(d, "presets", "320240")
        self.pr.mkdir(parents=True)
        self.bg = Path(d, "bg.png")
        vu.to_rgb(vu.solid(320, 240, (10, 80, 10, 255))).write_to_file(str(self.bg))
        self.fg = Path(d, "fg.png")
        vu.to_rgba(vu.solid(90, 90, (255, 255, 0, 255))).write_to_file(str(self.fg))
        self.theme = self.pr / "theme_1.yaml"
        self.theme.write_text(_theme_yaml(self.bg, self.fg))
        cfg = {"paths": {"service_config": d, "themes_dir": str(Path(d, "presets")),
                         "backgrounds_dir": d, "thumbnail_cache": str(Path(d, "thumbs"))},
               "supported_formats": {"images": [".png"]}}
        return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                                 "width": 320, "height": 240}], event_bus=None)

    def test_render_composite_differs_from_background_only(self):
        from thermalright_lcd_control.device_controller.display.config import (
            BackgroundType,
            DisplayConfig,
        )
        with TemporaryDirectory() as d:
            self._backend(d)
            cfg = DisplayConfig(background_path=str(self.bg), background_type=BackgroundType.IMAGE,
                                output_width=320, output_height=240,
                                foreground_image_path=str(self.fg),
                                foreground_position=(180, 120), foreground_alpha=1.0)
            composite = tr.render_theme_composite(str(self.bg), cfg, tr.THUMB_W, tr.THUMB_H)
            bg_only = tr.render_image(str(self.bg), tr.THUMB_W, tr.THUMB_H, keep_alpha=False)
            self.assertNotEqual(composite, bg_only)

    def test_get_themes_caches_composite(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            first = json.loads(be.get_themes())[0]["thumbnail"]     # placeholder
            be._thumbnail_worker.start()
            be._thumbnail_worker.flush()
            try:
                second = json.loads(be.get_themes())[0]["thumbnail"]  # composite
            finally:
                be._thumbnail_worker.stop()
            self.assertNotEqual(first, second)
            self.assertTrue(second.startswith("data:image/png;base64,"))

    def test_editing_theme_regenerates_thumbnail(self):
        with TemporaryDirectory() as d:
            be = self._backend(d)
            key1 = be._thumbnail_cache.key_for(str(self.theme), tr.THUMB_W, tr.THUMB_H, False)
            # rewrite the theme file → new mtime → new cache key (regeneration)
            os.utime(self.theme, (0, 0))
            key2 = be._thumbnail_cache.key_for(str(self.theme), tr.THUMB_W, tr.THUMB_H, False)
            self.assertNotEqual(key1, key2)


if __name__ == "__main__":
    unittest.main()
