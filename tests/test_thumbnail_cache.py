# SPDX-License-Identifier: Apache-2.0
import os

from thermalright_lcd_control.gui.components.thumbnail_cache import ThumbnailCache


def _write(p, data=b"x"):
    p.write_bytes(data)
    return str(p)


def test_key_is_none_for_missing_path(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    assert cache.key_for(str(tmp_path / "nope.png"), 160, 120, False) is None


def test_put_get_roundtrip(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    src = _write(tmp_path / "a.png")
    key = cache.key_for(src, 160, 120, False)
    assert cache.get(key) is None
    cache.put(key, b"PNGDATA")
    assert cache.get(key) == b"PNGDATA"


def test_key_changes_when_file_changes(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    src = tmp_path / "a.png"
    k1 = cache.key_for(_write(src, b"one"), 160, 120, False)
    os.utime(src, (1000, 1000))
    k2 = cache.key_for(_write(src, b"onelonger"), 160, 120, False)
    assert k1 != k2


def test_key_varies_with_dims_and_alpha(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    src = _write(tmp_path / "a.png")
    assert cache.key_for(src, 160, 120, False) != cache.key_for(src, 80, 60, False)
    assert cache.key_for(src, 160, 120, False) != cache.key_for(src, 160, 120, True)


def test_put_is_atomic_no_partial_file(tmp_path):
    cache = ThumbnailCache(str(tmp_path / "cache"))
    key = cache.key_for(_write(tmp_path / "a.png"), 160, 120, False)
    cache.put(key, b"DATA")
    leftovers = [p for p in (tmp_path / "cache").iterdir() if p.suffix == ".part"]
    assert leftovers == []
