# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import ctypes
import subprocess

_libc = None


def trim_native_heap() -> None:
    """Return freed heap pages to the OS after dropping a decoded clip.

    Freeing hundreds of PIL frames releases the Python objects but glibc keeps
    the pages in its arenas, so the process RSS never comes back down after a
    video theme is replaced by a static one. malloc_trim(0) hands those pages
    back. No-op on non-glibc platforms."""
    global _libc
    try:
        if _libc is None:
            _libc = ctypes.CDLL("libc.so.6")
        _libc.malloc_trim(0)
    except Exception:
        pass


def cap_malloc_arenas(n: int = 2) -> None:
    """Limit glibc to ``n`` malloc arenas (mallopt M_ARENA_MAX).

    By default glibc grows up to 8×ncores arenas as threads allocate
    concurrently (render loop per device + metrics + Qt), and every arena
    retains its own free pages — tens of MB of RSS that trim_native_heap()
    cannot return. Call once at startup, before worker threads spawn.
    No-op on non-glibc platforms."""
    global _libc
    try:
        if _libc is None:
            _libc = ctypes.CDLL("libc.so.6")
        _libc.mallopt(-8, int(n))   # M_ARENA_MAX = -8
    except Exception:
        pass


def _get_default_font_path():
    return _get_detailed_font_info()["file"]


def _get_detailed_font_info():
    formats = {
        "file": "%{file}",
        "fullname": "%{fullname}",
    }

    info = {}
    for key, format_str in formats.items():
        try:
            result = subprocess.check_output(
                ["fc-match", ":weight=bold", f"--format={format_str}"],
                text=True
            ).strip()
            info[key] = result
        except subprocess.CalledProcessError:
            info[key] = "Not available"

    return info
