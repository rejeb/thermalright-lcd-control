# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Encoded-frame cache shared by every device sink.

Keys are ``frame_idx`` only: every time metrics change the whole cache is
rebuilt at once (by RenderEngine on a background thread), so stale versions
never coexist with fresh ones and the overlay-version dimension is no longer
needed.
"""
from __future__ import annotations

import threading


class FrameEncodeCache:
    """Bounded cache of encoded device frames (holds at most one clip)."""

    def __init__(self, limit: int = 640):
        self._cache: dict[int, bytes] = {}
        self._limit = limit
        self._lock = threading.Lock()

    def set_frame_count(self, n_frames: int) -> None:
        """Size the cache to hold a whole clip (+margin) so a looping video
        re-encodes each frame only once per session, not once per loop."""
        self._limit = int(n_frames) + 2

    def get(self, frame_idx: int) -> bytes | None:
        with self._lock:
            return self._cache.get(frame_idx)

    def store(self, frame_idx: int, payload: bytes) -> None:
        """Insert an encoded frame. Evicts the oldest entry when over limit."""
        with self._lock:
            self._cache[frame_idx] = payload
            if len(self._cache) > self._limit:
                self._cache.pop(next(iter(self._cache)))

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)
