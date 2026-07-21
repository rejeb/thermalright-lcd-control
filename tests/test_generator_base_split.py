# SPDX-License-Identifier: Apache-2.0
"""Base/compose split: the cached base frames (bg+fg, unrotated) are JPEG
bytes; compose_device_frame decodes a fresh bitmap per miss, pastes the
overlay, and applies rotation on the device path only (the preview reads the
bytes as-is and stays unrotated)."""
import time
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator


def _jpeg(size=(4, 2), color=(10, 20, 30)) -> bytes:
    return vu.jpeg_bytes(vu.to_rgb(vu.solid(*size, (*color, 255))), quality=85)


def _make_generator(rotation=0, frames=None):
    """Build a generator with stubbed frames so no files/metrics are touched."""
    gen = DisplayGenerator.__new__(DisplayGenerator)
    gen.logger = mock.MagicMock()

    cfg = mock.MagicMock()
    cfg.output_width = 4
    cfg.output_height = 2
    cfg.rotation = rotation
    cfg.foreground_position = (0, 0)
    cfg.metrics_configs = []
    cfg.date_config = None
    cfg.time_config = None
    gen.config = cfg
    gen.text_renderer = mock.MagicMock()

    gen._metrics = None
    gen._metrics_snapshot = {}
    gen._foreground = None
    gen._frames = frames or [(_jpeg(), 2.0)]
    gen._frame_count_meta = len(gen._frames)
    gen._frame_duration_meta = gen._frames[0][1]
    gen.current_frame_index = 0
    gen.frame_start_time = time.time()
    gen._overlay = None
    gen._overlay_metrics = gen._metrics_snapshot
    gen._overlay_time_key = gen._time_key()
    gen._overlay_version = 0
    return gen


class TestBaseSplit(unittest.TestCase):
    def test_base_frame_is_cached_bytes_no_copy(self):
        gen = _make_generator()
        base = gen.get_base_frame()
        self.assertIsInstance(base, bytes)
        self.assertIs(base, gen._frames[0][0])   # same object, no copy
        # Same frame index → same object on repeated calls.
        self.assertIs(gen.get_base_frame(), base)

    def test_compose_decodes_and_applies_rotation(self):
        gen = _make_generator(rotation=90)
        base = gen.get_base_frame()
        out = gen.compose_device_frame(base)
        self.assertEqual(out.bands, 3)
        self.assertEqual((out.width, out.height), (2, 4))   # rotated on the device path

    def test_compose_yields_fresh_bitmap_per_call(self):
        gen = _make_generator()
        base = gen.get_base_frame()
        a = gen.compose_device_frame(base)
        b = gen.compose_device_frame(base)
        self.assertIsNot(a, b)                   # decode → caller owns the bitmap

    def test_get_frame_with_metrics_returns_rgb(self):
        gen = _make_generator()
        out = gen.get_frame_with_metrics()
        self.assertEqual(out.bands, 3)
        self.assertEqual((out.width, out.height), (4, 2))

    def test_compose_pastes_overlay(self):
        gen = _make_generator(frames=[(_jpeg(color=(0, 0, 0)), 2.0)])
        gen._overlay = vu.solid(4, 2, (255, 255, 255, 255))
        out = gen.compose_device_frame(gen.get_base_frame())
        r, g, b = vu.to_numpy(out)[1, 1]
        self.assertTrue(r > 240 and g > 240 and b > 240)   # overlay applied

    def test_refresh_overlay_keeps_frames_and_bumps_version(self):
        gen = _make_generator()
        frames = gen._frames
        v0 = gen._overlay_version
        new_cfg = mock.MagicMock()
        new_cfg.output_width = 4
        new_cfg.output_height = 2
        new_cfg.rotation = 0
        new_cfg.global_font_path = None
        new_cfg.metrics_configs = []
        new_cfg.date_config = None
        new_cfg.time_config = None
        with mock.patch("thermalright_lcd_control.device_controller.display."
                        "generator.TextRenderer", return_value=mock.MagicMock()):
            gen.refresh_overlay(new_cfg)
        self.assertIs(gen._frames, frames)              # cached frames kept
        self.assertIs(gen.config, new_cfg)
        self.assertEqual(gen._overlay_version, v0 + 1)  # encode cache invalidates


def test_sync_overlay_rebuilds_only_when_stale():
    gen = _make_generator()
    v0 = gen._overlay_version
    assert gen.sync_overlay() == v0          # nothing changed → no bump
    gen._metrics = mock.MagicMock()
    gen._metrics.values.return_value = {"cpu": 1}   # new dict identity
    assert gen.sync_overlay() == v0 + 1      # stale → rebuilt + bumped


if __name__ == "__main__":
    unittest.main()
