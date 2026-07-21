# SPDX-License-Identifier: Apache-2.0
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from thermalright_lcd_control.device_controller.display import vips_utils as vu  # noqa: E402
from thermalright_lcd_control.gui.backend.app_backend import AppBackend  # noqa: E402
from thermalright_lcd_control.gui.components import thumbnail_render as tr  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _backend(cfg_dir, cache_dir):
    _app()
    cfg = {"paths": {"service_config": str(cfg_dir), "themes_dir": str(cfg_dir),
                     "backgrounds_dir": str(cfg_dir),
                     "thumbnail_cache": str(cache_dir)},
           "supported_formats": {"images": [".png"], "videos": [".mp4"]}}
    return AppBackend(cfg, [{"id": "dev1", "vid": 0x0416, "pid": 0x5302,
                             "width": 320, "height": 240}], event_bus=None)


def test_cache_miss_returns_placeholder_and_enqueues(tmp_path):
    cache_dir = tmp_path / "cache"
    src = tmp_path / "a.png"
    vu.to_rgb(vu.solid(40, 30, (9, 9, 9, 255))).write_to_file(str(src))
    be = _backend(tmp_path, cache_dir)
    enq = []
    be._thumbnail_worker.enqueue = lambda *a, **k: enq.append(a)   # stub

    url = be._thumbnail_for(str(src))

    assert url.startswith("data:image/png;base64,")     # a placeholder gradient
    assert enq and enq[0][0] == str(src)                # enqueued the real work


def test_cache_hit_returns_cached_bytes(tmp_path):
    cache_dir = tmp_path / "cache"
    src = tmp_path / "a.png"
    vu.to_rgb(vu.solid(40, 30, (9, 9, 9, 255))).write_to_file(str(src))
    be = _backend(tmp_path, cache_dir)
    key = be._thumbnail_cache.key_for(str(src), tr.THUMB_W, tr.THUMB_H, False)
    be._thumbnail_cache.put(key, tr.gradient(1, tr.THUMB_W, tr.THUMB_H))

    called = []
    be._thumbnail_worker.enqueue = lambda *a, **k: called.append(a)
    url = be._thumbnail_for(str(src))

    assert url == tr.data_url(be._thumbnail_cache.get(key))
    assert called == []                                 # no work enqueued on a hit


def test_missing_path_returns_placeholder_without_enqueue(tmp_path):
    be = _backend(tmp_path, tmp_path / "cache")
    called = []
    be._thumbnail_worker.enqueue = lambda *a, **k: called.append(a)
    url = be._thumbnail_for(str(tmp_path / "nope.png"))
    assert url.startswith("data:image/png;base64,")
    assert called == []
