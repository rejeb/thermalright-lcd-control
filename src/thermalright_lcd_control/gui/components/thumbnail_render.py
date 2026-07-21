# SPDX-License-Identifier: Apache-2.0
"""Pure thumbnail rendering: image / video → 160x120 PNG bytes.

No Qt and no backend state, so both the GUI thread and the background
ThumbnailWorker share one implementation.
"""
from __future__ import annotations

import base64

import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu

THUMB_W, THUMB_H = 160, 120

# Bumped whenever render_theme_composite's output changes, so stale cached theme
# thumbnails (keyed only on the theme file's mtime) are regenerated.
COMPOSITE_VERSION = "theme-composite-v2"


def _contain(img: pyvips.Image, w: int, h: int) -> pyvips.Image:
    """Shrink to fit entirely within the box (object-fit: contain), centred on a
    transparent background — keeps aspect ratio, shows the whole layer."""
    scale = min(w / img.width, h / img.height)
    resized = vu.to_rgba(img.resize(scale, kernel="lanczos3"))
    canvas = vu.solid(w, h, (0, 0, 0, 0))
    return vu.overlay_at(canvas, resized, (w - resized.width) // 2,
                         (h - resized.height) // 2)


def render_image(path: str, w: int, h: int, keep_alpha: bool) -> bytes:
    """Load an image (or first GIF frame) → PNG bytes. ``keep_alpha`` keeps
    transparency and fits the whole layer (contain); otherwise centre-crops
    (cover)."""
    if keep_alpha:
        img = _contain(vu.load_file(path), w, h)
    else:
        img = vu.to_rgb(pyvips.Image.thumbnail(path, w, height=h, crop="centre"))
    return vu.png_bytes(img)


def render_video(path: str, w: int, h: int) -> bytes:
    """First frame of a video → PNG bytes (cover)."""
    import cv2
    cap = cv2.VideoCapture(path)
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise ValueError(f"no frame decoded from {path}")
        img = vu.from_numpy(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img = img.thumbnail_image(w, height=h, crop="centre")
        return vu.png_bytes(img)
    finally:
        cap.release()


def render_theme_composite(bg_path: str, cfg, w: int, h: int) -> bytes:
    """Compose a full theme preview → PNG bytes: background + foreground + text
    overlays (metrics/texts/date/time), rendered at the theme resolution and then
    shrunk to the thumbnail box (cover). ``cfg`` is a DisplayConfig; metrics use a
    representative sample value so a value is shown. Never downloads media — the
    caller passes an already-resolved local background image path."""
    import os
    from datetime import datetime

    from thermalright_lcd_control.device_controller.display.text_renderer import (
        TextRenderer,
    )

    W = int(getattr(cfg, "output_width", 0) or 0) or 320
    H = int(getattr(cfg, "output_height", 0) or 0) or 240

    # 1) background at the theme resolution (cover), or black if none
    if bg_path and os.path.exists(bg_path):
        base = vu.to_rgba(pyvips.Image.thumbnail(bg_path, W, height=H, crop="centre"))
    else:
        base = vu.solid(W, H, (0, 0, 0, 255))

    # 2) foreground (same prep as DisplayGenerator: alpha then paste at position)
    fg_path = getattr(cfg, "foreground_image_path", None)
    if fg_path and os.path.exists(fg_path):
        try:
            fg = vu.load_file(fg_path)
            alpha = float(getattr(cfg, "foreground_alpha", 1.0) or 1.0)
            if alpha < 1.0:
                fg = fg[0:3].bandjoin((fg[3] * alpha).cast("uchar"))
            fx, fy = getattr(cfg, "foreground_position", (0, 0)) or (0, 0)
            base = vu.overlay_at(base, fg, int(fx), int(fy))
        except Exception:
            pass

    # 3) text overlays (metrics with a sample value, standalone texts, date, time)
    try:
        tr = TextRenderer()
        overlay = vu.solid(W, H, (0, 0, 0, 0))
        configs = getattr(cfg, "metrics_configs", None) or []
        sample = {c.name: 42 for c in configs if getattr(c, "enabled", False)}
        now = datetime.now()
        overlay = tr.render_metrics(overlay, sample, configs)
        overlay = tr.render_texts(overlay, getattr(cfg, "texts", None))
        overlay = tr.render_date(overlay, getattr(cfg, "date_config", None), now)
        overlay = tr.render_time(overlay, getattr(cfg, "time_config", None), now)
        overlay = tr.render_weekday(overlay, getattr(cfg, "weekday_config", None), now)
        base = vu.overlay_at(base, overlay, 0, 0)
    except Exception:
        pass

    # 4) resize the whole composed frame to fit inside the thumbnail box,
    #    aspect ratio preserved (no crop, no letterbox padding — the card centres it)
    scale = min(w / base.width, h / base.height)
    return vu.png_bytes(vu.to_rgb(base.resize(scale, kernel="lanczos3")))


def gradient(hue: int, w: int, h: int) -> bytes:
    """Diagonal gradient placeholder → PNG bytes."""
    import colorsys

    import numpy as np

    def _hsl(hue_deg, s, lightness):
        r, g, b = colorsys.hls_to_rgb(hue_deg / 360.0, lightness, s)
        return int(r * 255), int(g * 255), int(b * 255)

    top = np.array(_hsl(hue, 0.55, 0.72), dtype=np.float32)
    bot = np.array(_hsl((hue + 28) % 360, 0.50, 0.35), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = ((xx + yy) / max(1, w + h - 2))[..., None]
    rgb = (top + (bot - top) * t).astype(np.uint8)
    return vu.png_bytes(vu.from_numpy(rgb))


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
