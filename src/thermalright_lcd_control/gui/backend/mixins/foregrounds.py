# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Foreground library slots: list/add/select/clear/delete (images only).

Mixed into :class:`AppBackend`; reads ``self.foregrounds_dir``,
``self.preview_manager``, ``self._window`` and the ``foreground_added``/
``error_occurred`` signals, and uses the media/thumbnail helpers.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from thermalright_lcd_control.common.media_formats import IMAGE_EXTENSIONS


class ForegroundMixin:
    def get_foregrounds(self) -> str:
        """JSON: [{name, path, removable, thumbnail}] (images only).

        User-added foregrounds (``user_`` prefix) are listed first and marked
        removable.
        """
        items: list[dict[str, str]] = []
        if self.foregrounds_dir.exists():
            entries = sorted(
                self.foregrounds_dir.iterdir(),
                key=lambda p: (not p.name.startswith("user_"), p.name.lower()))
            for entry in entries:
                if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
                    items.append({
                        "name": entry.name,
                        "path": str(entry.absolute()),
                        "removable": entry.name.startswith("user_"),
                        "thumbnail": self._thumbnail_from_image(str(entry), keep_alpha=True),
                    })
        return json.dumps(items)

    def _rotated_foregrounds_dir(self) -> Path:
        """``<h><w>`` sibling of ``foregrounds_dir`` (media dir used in 90°/270°)."""
        cur = self.foregrounds_dir
        w, h = self._media_res()
        return cur.parent / f"{h}{w}"

    def add_foreground(self) -> None:
        """Native QFileDialog (single selection, images only). Copies into
        ``foregrounds_dir`` prefixed ``user_`` (plus a copy in the rotated
        ``<h><w>`` folder), then emits ``foreground_added``."""
        path, _ = QFileDialog.getOpenFileName(
            self._window, "Add foreground", str(self.foregrounds_dir.absolute()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        try:
            self.foregrounds_dir.mkdir(parents=True, exist_ok=True)
            src = Path(path)
            dest = self.foregrounds_dir / f"user_{src.name}"
            shutil.copy2(src, dest)
            rotated = self._rotated_foregrounds_dir()
            if rotated != self.foregrounds_dir:
                rotated.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, rotated / dest.name)
            self.foreground_added.emit()
        except Exception as e:
            self.logger.error(f"add foreground failed: {e}")
            self.error_occurred.emit(f"Add foreground failed: {e}")

    def delete_foreground(self, path: str) -> None:
        """Delete a user-added foreground (a ``user_`` file). Confirms, deletes the
        themes that use it, and — if the foreground was active — clears it +
        applies before removing the file."""
        try:
            p = Path(path).resolve()
            fg_dir = self.foregrounds_dir.resolve()
            if p.parent != fg_dir:
                raise ValueError("target outside the foregrounds folder")
            if not p.name.startswith("user_"):
                raise ValueError("default foreground is not removable")

            def _reset_if_in_use() -> None:
                cur = self.preview_manager.current_foreground_path
                if cur and self._same_path(cur, p):
                    self.preview_manager.clear_foreground()   # disable the foreground
                    self.apply()                              # push the new config
                    self._emit_theme_loaded()                 # sync the Foreground toggle

            self._delete_media_with_themes(p, "foreground", _reset_if_in_use)
            rotated = self._rotated_foregrounds_dir() / p.name
            if rotated.resolve() != p and rotated.exists():
                rotated.unlink()
        except Exception as e:
            self.logger.error(f"delete_foreground failed: {e}")
            self.error_occurred.emit(f"Delete failed: {e}")

    def select_foreground(self, path: str) -> None:
        try:
            self.preview_manager.set_foreground(path)
            self._publish_live()
            self._emit_theme_loaded()       # UI: sync the Foreground toggle
        except Exception as e:
            self.logger.error(f"select_foreground failed: {e}")
            self.error_occurred.emit(f"Foreground error: {e}")

    def clear_foreground(self) -> None:
        self.preview_manager.clear_foreground()
        self._publish_live()
        self._emit_theme_loaded()           # UI: sync the Foreground toggle
