# SPDX-License-Identifier: Apache-2.0
"""Disk-backed thumbnail cache.

Keyed by absolute path + mtime + size + target dims + alpha, so an edited or
replaced file yields a fresh key and is regenerated automatically (the old
entry is orphaned). Values are the raw PNG bytes stored as ``<key>.png``.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


class ThumbnailCache:
    def __init__(self, cache_dir: str):
        self._dir = Path(cache_dir)

    def key_for(self, path: str, w: int, h: int, keep_alpha: bool,
                variant: str = "") -> str | None:
        try:
            st = os.stat(path)
        except OSError:
            return None
        # ``variant`` lets a render mode (e.g. the theme composite) bust its own
        # cached entries when its rendering changes, independently of the file.
        raw = (f"{os.path.abspath(path)}\0{st.st_mtime_ns}\0{st.st_size}\0"
               f"{w}x{h}\0{int(keep_alpha)}\0{variant}")
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _file(self, key: str) -> Path:
        return self._dir / f"{key}.png"

    def get(self, key: str) -> bytes | None:
        try:
            return self._file(key).read_bytes()
        except OSError:
            return None

    def put(self, key: str, png: bytes) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        dest = self._file(key)
        tmp = dest.with_suffix(".png.part")
        try:
            tmp.write_bytes(png)
            os.replace(tmp, dest)
        finally:
            if tmp.exists():
                tmp.unlink()
