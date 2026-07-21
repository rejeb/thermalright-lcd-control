# SPDX-License-Identifier: Apache-2.0
"""Background thumbnail generation.

A single daemon thread drains a queue of render requests, writes results to the
ThumbnailCache, and fires a debounced ``on_progress`` callback so the GUI can
refresh. Never touches Qt widgets — ``on_progress`` is expected to be a
thread-safe trigger (e.g. a Qt Signal's ``emit``, delivered queued).
"""
from __future__ import annotations

import queue
import threading
import time

from thermalright_lcd_control.common.logging_config import get_gui_logger
from thermalright_lcd_control.gui.components import thumbnail_render as tr
from thermalright_lcd_control.gui.components.thumbnail_cache import ThumbnailCache

_SENTINEL = object()


class ThumbnailWorker:
    def __init__(self, cache: ThumbnailCache, on_progress, debounce: float = 0.15):
        self._cache = cache
        self._on_progress = on_progress
        self._debounce = debounce
        self._q: queue.Queue = queue.Queue()
        self._inflight: set[str] = set()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._logger = get_gui_logger()
        self._last_emit = 0.0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="thumbnail-worker", daemon=True)
        self._thread.start()

    def enqueue(self, path: str, w: int, h: int, keep_alpha: bool, is_video: bool) -> None:
        key = self._cache.key_for(path, w, h, keep_alpha)
        if key is None:
            return
        with self._lock:
            if key in self._inflight or self._cache.get(key) is not None:
                return
            self._inflight.add(key)
        self._q.put(("media", key, path, w, h, keep_alpha, is_video))

    def enqueue_composite(self, key: str, bg_path: str, cfg, w: int, h: int) -> None:
        """Queue a full theme-preview composite (background + foreground +
        overlays). ``key`` is precomputed by the caller (keyed on the theme file),
        ``cfg`` is the theme's DisplayConfig."""
        with self._lock:
            if key in self._inflight or self._cache.get(key) is not None:
                return
            self._inflight.add(key)
        self._q.put(("theme", key, bg_path, cfg, w, h))

    def flush(self) -> None:
        """Test helper: block until the queue is drained."""
        self._q.join()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._q.put(_SENTINEL)
        self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item is _SENTINEL:
                    return
                self._process(item)
            finally:
                self._q.task_done()

    def _process(self, item) -> None:
        kind, key = item[0], item[1]
        try:
            if kind == "theme":
                _, _, bg_path, cfg, w, h = item
                png = tr.render_theme_composite(bg_path, cfg, w, h)
            else:
                _, _, path, w, h, keep_alpha, is_video = item
                png = (tr.render_video(path, w, h) if is_video
                       else tr.render_image(path, w, h, keep_alpha))
            self._cache.put(key, png)
            self._maybe_emit()
        except Exception as e:
            self._logger.debug(f"thumbnail render failed ({kind}): {e}")
        finally:
            with self._lock:
                self._inflight.discard(key)

    def _maybe_emit(self) -> None:
        now = time.monotonic()
        if now - self._last_emit >= self._debounce:
            self._last_emit = now
            try:
                self._on_progress()
            except Exception as e:
                self._logger.debug(f"thumbnail on_progress failed: {e}")
