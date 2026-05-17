# SPDX-License-Identifier: Apache-2.0
"""Device encode-cache refresh rules (overlay staleness granularity):

- no widgets at all (no metrics, no date, no time) → never refresh until the
  config changes;
- only a date widget → refresh at midnight (day change), not every minute;
- every other case (time widget and/or metrics) keeps the minute cadence.
"""
import time
from datetime import datetime
from unittest import mock

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator


def _jpeg():
    return vu.jpeg_bytes(vu.to_rgb(vu.solid(4, 2, (10, 20, 30, 255))), quality=85)


def _widget(enabled=True):
    w = mock.MagicMock()
    w.enabled = enabled
    return w


def _make_generator(metrics=False, date=False, time_w=False):
    gen = DisplayGenerator.__new__(DisplayGenerator)
    gen.logger = mock.MagicMock()
    cfg = mock.MagicMock()
    cfg.output_width, cfg.output_height = 4, 2
    cfg.rotation = 0
    cfg.metrics_configs = [mock.MagicMock()] if metrics else []
    cfg.date_config = _widget() if date else None
    cfg.time_config = _widget() if time_w else None
    gen.config = cfg
    gen.text_renderer = mock.MagicMock()
    gen.text_renderer.render_metrics.side_effect = lambda ov, *_: ov
    gen.text_renderer.render_date.side_effect = lambda ov, *_: ov
    gen.text_renderer.render_time.side_effect = lambda ov, *_: ov
    gen._metrics = None
    gen._metrics_snapshot = {}
    gen._foreground = None
    gen._frames = [(_jpeg(), 2.0)]
    gen._frame_count_meta = 1
    gen._frame_duration_meta = 2.0
    gen.current_frame_index = 0
    gen.frame_start_time = time.time()
    gen._overlay = None
    gen._overlay_metrics = gen._metrics_snapshot
    gen._overlay_time_key = gen._time_key()
    gen._overlay_version = 0
    return gen


def _sync_at(gen, dt: datetime) -> int:
    with mock.patch("thermalright_lcd_control.device_controller.display."
                    "generator.datetime") as m:
        m.now.return_value = dt
        return gen.sync_overlay()


def test_no_widgets_never_refreshes_across_minutes_and_days():
    gen = _make_generator()
    v0 = gen._overlay_version
    assert _sync_at(gen, datetime(2026, 7, 12, 10, 0)) == v0
    assert _sync_at(gen, datetime(2026, 7, 12, 10, 1)) == v0     # minute rollover
    assert _sync_at(gen, datetime(2026, 7, 13, 0, 0)) == v0      # midnight rollover


def test_date_only_refreshes_at_midnight_not_each_minute():
    gen = _make_generator(date=True)
    with mock.patch("thermalright_lcd_control.device_controller.display."
                    "generator.datetime") as m:
        m.now.return_value = datetime(2026, 7, 12, 23, 58)
        gen._overlay_time_key = gen._time_key()
        v0 = gen.sync_overlay()
    assert _sync_at(gen, datetime(2026, 7, 12, 23, 59)) == v0    # minute → no refresh
    assert _sync_at(gen, datetime(2026, 7, 13, 0, 0)) == v0 + 1  # midnight → refresh


def test_time_widget_keeps_minute_cadence():
    gen = _make_generator(time_w=True)
    with mock.patch("thermalright_lcd_control.device_controller.display."
                    "generator.datetime") as m:
        m.now.return_value = datetime(2026, 7, 12, 10, 0)
        gen._overlay_time_key = gen._time_key()
        v0 = gen.sync_overlay()
    assert _sync_at(gen, datetime(2026, 7, 12, 10, 1)) == v0 + 1


def test_metrics_only_keeps_minute_cadence():
    gen = _make_generator(metrics=True)
    with mock.patch("thermalright_lcd_control.device_controller.display."
                    "generator.datetime") as m:
        m.now.return_value = datetime(2026, 7, 12, 10, 0)
        gen._overlay_time_key = gen._time_key()
        v0 = gen.sync_overlay()
    assert _sync_at(gen, datetime(2026, 7, 12, 10, 1)) == v0 + 1
