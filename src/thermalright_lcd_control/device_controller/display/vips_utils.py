# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Shared pyvips helpers: conversions, canvases, codecs, geometry.

All display-pipeline images are pyvips.Image, 8-bit, 3 (RGB) or 4 (RGBA)
bands, sRGB. numpy appears only at the RGB565 wire boundary."""
import os

import numpy as np
import pyvips

# libvips defaults target large-image throughput: a worker-thread pool per
# operation and a 100-op/100 MB operation cache. On 320-480 px LCD frames the
# pool doubles CPU and the cache inflates RSS by tens of MB, so pin both down.
# pyvips's compiled cffi wrapper doesn't expose vips_concurrency_set, so reach
# the (already loaded) shared library directly; dlopen-ing the same file
# returns the same handle, so the setting applies process-wide.


def _pin_concurrency(n: int) -> None:
    import ctypes.util
    import glob

    candidates = glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(pyvips.__file__)),
        "pyvips_binary.libs", "libvips*.so*"))
    if not candidates:
        found = ctypes.util.find_library("vips")
        candidates = [found] if found else []
    for path in candidates:
        try:
            ctypes.CDLL(path).vips_concurrency_set(n)
            return
        except (OSError, AttributeError):
            continue


_pin_concurrency(1)
pyvips.cache_set_max(0)


def to_numpy(img: pyvips.Image) -> np.ndarray:
    """(H, W, bands) uint8 view of ``img`` (materializes the pipeline)."""
    return np.ndarray(buffer=img.write_to_memory(), dtype=np.uint8,
                      shape=(img.height, img.width, img.bands))


def from_numpy(arr: np.ndarray) -> pyvips.Image:
    if arr.ndim == 2:
        arr = arr[:, :, None]
    h, w, bands = arr.shape
    return pyvips.Image.new_from_memory(
        np.ascontiguousarray(arr, dtype=np.uint8).tobytes(), w, h, bands, "uchar")


def solid(width: int, height: int, rgba: tuple) -> pyvips.Image:
    """Uniform RGBA canvas (test/builder helper)."""
    r, g, b = rgba[0], rgba[1], rgba[2]
    a = rgba[3] if len(rgba) > 3 else 255
    return ((pyvips.Image.black(width, height, bands=4) + [r, g, b, a])
            .cast("uchar").copy(interpretation="srgb"))


def to_rgba(img: pyvips.Image) -> pyvips.Image:
    if img.hasalpha():
        return img if img.bands == 4 else img.colourspace("srgb")
    if img.bands == 1:
        img = img.colourspace("srgb")
    return img.addalpha()


def to_rgb(img: pyvips.Image) -> pyvips.Image:
    if img.hasalpha():
        img = img.flatten(background=[0, 0, 0])
    if img.bands == 1:
        img = img.colourspace("srgb")
    return img


def jpeg_bytes(img: pyvips.Image, quality: int = 85) -> bytes:
    return to_rgb(img).jpegsave_buffer(Q=quality)


def from_jpeg(data: bytes) -> pyvips.Image:
    return pyvips.Image.jpegload_buffer(data)


def png_bytes(img: pyvips.Image) -> bytes:
    return img.pngsave_buffer()


def load_file(path: str) -> pyvips.Image:
    """Random-access RGBA load (safe to reuse pixels many times)."""
    return to_rgba(pyvips.Image.new_from_file(path, access="random"))


def resize_to(img: pyvips.Image, w: int, h: int) -> pyvips.Image:
    """Exact-size stretch, lanczos3 (PIL resize(LANCZOS) equivalent)."""
    if (img.width, img.height) == (w, h):
        return img
    return img.resize(w / img.width, vscale=h / img.height, kernel="lanczos3")


def overlay_at(base: pyvips.Image, over: pyvips.Image, x: int, y: int) -> pyvips.Image:
    """Alpha-composite ``over`` onto ``base`` at (x, y)."""
    return to_rgba(base).composite2(to_rgba(over), "over", x=x, y=y)


def rotate(img: pyvips.Image, degrees: int) -> pyvips.Image:
    """Clockwise rotation by 0/90/180/270 (matches the config's semantics)."""
    if degrees == 90:
        return img.rot90()
    if degrees == 180:
        return img.rot180()
    if degrees == 270:
        return img.rot270()
    return img
