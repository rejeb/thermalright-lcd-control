# SPDX-License-Identifier: Apache-2.0
import threading

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.gui.components.thumbnail_cache import ThumbnailCache
from thermalright_lcd_control.gui.components.thumbnail_worker import ThumbnailWorker


def _img(tmp_path, name="a.png"):
    p = tmp_path / name
    vu.to_rgb(vu.solid(64, 48, (1, 2, 3, 255))).write_to_file(str(p))
    return str(p)


def test_worker_populates_cache_and_signals(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    progressed = threading.Event()
    w = ThumbnailWorker(cache, on_progress=progressed.set, debounce=0.0)
    w.start()
    try:
        src = _img(tmp_path)
        key = cache.key_for(src, 160, 120, False)
        w.enqueue(src, 160, 120, False, is_video=False)
        w.flush()
    finally:
        w.stop()
    assert cache.get(key) is not None
    assert progressed.wait(2.0)


def test_worker_skips_already_cached(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    src = _img(tmp_path)
    key = cache.key_for(src, 160, 120, False)
    cache.put(key, b"PRECACHED")
    w = ThumbnailWorker(cache, on_progress=lambda: None, debounce=0.0)
    w.start()
    try:
        w.enqueue(src, 160, 120, False, is_video=False)
        w.flush()
    finally:
        w.stop()
    assert cache.get(key) == b"PRECACHED"   # not overwritten


def test_worker_survives_bad_path(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    w = ThumbnailWorker(cache, on_progress=lambda: None, debounce=0.0)
    w.start()
    try:
        w.enqueue(str(tmp_path / "missing.png"), 160, 120, False, is_video=False)
        w.flush()                            # must not raise / hang
    finally:
        w.stop()
