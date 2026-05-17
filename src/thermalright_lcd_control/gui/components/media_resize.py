# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Pure media resize helpers (no Qt).

Resize an image / gif / video to a target device resolution. Videos longer than
``MAX_VIDEO_SECONDS`` are rejected (no file written — no truncation). Video output is
always an mp4 container at the source fps; image keeps its extension; gif stays a gif.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu

MAX_VIDEO_SECONDS = 5.0
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
_GIF_EXT = {".gif"}
_VIDEO_EXT = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v"}


class MediaTooLongError(Exception):
    """Raised when a video exceeds ``MAX_VIDEO_SECONDS``."""


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except (TypeError, ValueError):
        return 0.0


def resize_image(src: Path, dst: Path, w: int, h: int) -> Path:
    img = vu.to_rgb(vu.resize_to(
        pyvips.Image.new_from_file(str(src), access="random"), w, h))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.write_to_file(str(dst))
    return dst


def resize_gif(src: Path, dst: Path, w: int, h: int) -> Path:
    anim = pyvips.Image.new_from_file(str(src), n=-1, access="random")
    page_h = anim.get("page-height") if anim.get_typeof("page-height") else anim.height
    out = anim.resize(w / anim.width, vscale=h / page_h, kernel="lanczos3").copy()
    out.set_type(pyvips.GValue.gint_type, "page-height", h)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.write_to_file(str(dst))          # delays/loop metadata carried through
    return dst


def resize_video(src: Path, dst: Path, w: int, h: int) -> Path:
    if probe_duration(src) > MAX_VIDEO_SECONDS:
        raise MediaTooLongError(
            f"Video longer than {MAX_VIDEO_SECONDS:.0f}s; please use a shorter clip.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    # garder l'extension de sortie sur le temporaire pour que ffmpeg déduise le conteneur
    tmp = dst.with_suffix(".part" + dst.suffix)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vf", f"scale={w}:{h}",
             "-fps_mode", "passthrough", "-an", str(tmp)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tmp.replace(dst)
    finally:
        if tmp.exists():
            tmp.unlink()
    return dst


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in (_IMAGE_EXT | _GIF_EXT | _VIDEO_EXT)


def materialize(src: Path, dest_stem: Path, w: int, h: int) -> Path:
    """Resize ``src`` to ``w×h`` at ``dest_stem`` (path WITHOUT suffix); the suffix is
    chosen per type (gif→.gif, video→.mp4, image keeps its own)."""
    ext = src.suffix.lower()
    if ext in _GIF_EXT:
        return resize_gif(src, dest_stem.with_suffix(".gif"), w, h)
    if ext in _VIDEO_EXT:
        return resize_video(src, dest_stem.with_suffix(".mp4"), w, h)
    if ext in _IMAGE_EXT:
        return resize_image(src, dest_stem.with_suffix(ext), w, h)
    raise ValueError(f"unsupported media type: {src.name}")
