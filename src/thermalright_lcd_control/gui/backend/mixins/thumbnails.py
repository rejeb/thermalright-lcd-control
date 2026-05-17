# SPDX-License-Identifier: Apache-2.0
"""Thumbnail resolution: cache-first, generation delegated to a background
worker. A cache miss returns a gradient placeholder immediately and enqueues the
real render — the Qt main thread never decodes an image here."""
from __future__ import annotations

from pathlib import Path

from thermalright_lcd_control.gui.components import thumbnail_render as tr


class ThumbnailMixin:
    """Reads ``self.config``/``self.logger``, ``self._thumbnail_cache``,
    ``self._thumbnail_worker`` and ``self._first_collection_image`` from the host
    (AppBackend)."""

    def _video_exts(self) -> set[str]:
        fmts = self.config.get("supported_formats", {})
        return set(fmts.get("videos", [".mp4", ".avi", ".mkv", ".mov", ".webm"]))

    def _thumbnail_for(self, path: str) -> str:
        """Cache-first thumbnail for image / video / gif / collection."""
        if not path:
            return self._thumbnail_gradient(206)
        p = Path(path)
        try:
            if p.is_dir():
                first = self._first_collection_image(p)
                return (self._cached_or_placeholder(str(first), False, False)
                        if first else self._thumbnail_gradient(150))
            is_video = p.suffix.lower() in self._video_exts()
            return self._cached_or_placeholder(str(p), False, is_video)
        except Exception as e:
            self.logger.warning(f"Thumbnail failed for {path}: {e}")
            return self._thumbnail_gradient(206)

    def _theme_thumbnail(self, yaml_path, cfg, bg_path: str) -> str:
        """Cache-first COMPOSITE preview for a theme (background + foreground +
        widgets). Keyed on the theme file (its mtime), so editing/saving a theme
        regenerates it. A cache miss enqueues the composite and shows a
        placeholder until the worker finishes."""
        from pathlib import Path
        if cfg is None:
            return self._thumbnail_for(bg_path)     # fallback: background only
        key = self._thumbnail_cache.key_for(
            str(Path(yaml_path)), tr.THUMB_W, tr.THUMB_H, False,
            variant=tr.COMPOSITE_VERSION)
        if key is None:
            return self._thumbnail_gradient(206)
        cached = self._thumbnail_cache.get(key)
        if cached is not None:
            return tr.data_url(cached)
        self._thumbnail_worker.enqueue_composite(
            key, bg_path, cfg, tr.THUMB_W, tr.THUMB_H)
        return self._thumbnail_gradient(206)

    def _thumbnail_from_image(self, image_path: str, keep_alpha: bool = False) -> str:
        """Cache-first image thumbnail (foregrounds pass ``keep_alpha=True``)."""
        if not image_path:
            return self._thumbnail_gradient(206)
        return self._cached_or_placeholder(str(image_path), keep_alpha, False)

    def _cached_or_placeholder(self, path: str, keep_alpha: bool, is_video: bool) -> str:
        key = self._thumbnail_cache.key_for(path, tr.THUMB_W, tr.THUMB_H, keep_alpha)
        if key is None:                                  # missing / unstatable
            return self._thumbnail_gradient(206)
        cached = self._thumbnail_cache.get(key)
        if cached is not None:
            return tr.data_url(cached)
        self._thumbnail_worker.enqueue(path, tr.THUMB_W, tr.THUMB_H, keep_alpha, is_video)
        return self._thumbnail_gradient(28 if is_video else 206)

    def _thumbnail_gradient(self, hue: int) -> str:
        return tr.data_url(tr.gradient(hue, tr.THUMB_W, tr.THUMB_H))
