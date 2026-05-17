# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Shared media helpers: classify media, find themes using a file, cascade delete.

Mixed into :class:`AppBackend`; reads ``self.config``, ``self.backgrounds_dir``,
``self.dev_width``/``self.dev_height``, ``self._window`` and the
``themes_refreshed`` signal, and calls the theme helpers (``_yaml_files``,
``_display_name``) from the host.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from thermalright_lcd_control.common.media_formats import IMAGE_EXTENSIONS


class MediaHelpersMixin:
    def _delete_media_with_themes(self, target: Path, kind_label: str, reset_if_in_use) -> None:
        """Confirm + delete a user media file and the themes that use it.

        ``reset_if_in_use`` switches/applies the config when the media is active;
        it is called BEFORE any file is removed."""
        affected = self._themes_using(target)
        msg = [f"Delete this {kind_label}?"]
        if affected:
            names = "\n".join(f"  • {self._display_name(p)}" for p in affected)
            plural = "themes" if len(affected) > 1 else "theme"
            msg += ["",
                    f"{len(affected)} saved {plural} using this {kind_label} "
                    f"will also be deleted:",
                    names]
        if not self._confirm("Confirm deletion", "\n".join(msg)):
            return

        # 1) the config must not point at a deleted file → reset + apply first
        reset_if_in_use()
        # 2) delete the impacted themes
        for yaml_path in affected:
            try:
                yaml_path.unlink()
            except Exception as e:
                self.logger.warning(f"cannot delete theme {yaml_path}: {e}")
        # 3) delete the media itself
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        # 4) refresh the themes grid if any were removed
        if affected:
            self.themes_refreshed.emit()

    def _themes_using(self, target: Path) -> list[Path]:
        """Theme YAMLs referencing ``target`` (as background or foreground)."""
        from thermalright_lcd_control.device_controller.display.config_loader import ConfigLoader
        loader = ConfigLoader()
        using: list[Path] = []
        for yaml_path in self._yaml_files():
            try:
                cfg = loader.load_config(str(yaml_path), self.dev_width, self.dev_height)
            except Exception:
                continue
            if any(ref and self._same_path(ref, target)
                   for ref in (cfg.background_path, cfg.foreground_image_path)):
                using.append(yaml_path)
        return using

    @staticmethod
    def _same_path(a, b) -> bool:
        try:
            return Path(a).resolve() == Path(b).resolve()
        except Exception:
            return False

    def _first_background(self, exclude: Path) -> str | None:
        """Absolute path of the first background in the grid (excluding ``exclude``)."""
        bg_dir = Path(self.backgrounds_dir)
        if not bg_dir.exists():
            return None

        def _is_user(p: Path) -> bool:
            return p.name.startswith("user_") or p.name.startswith("collection_")

        entries = sorted(bg_dir.iterdir(),
                         key=lambda p: (not _is_user(p), p.name.lower()))
        for e in entries:
            if self._same_path(e, exclude):
                continue
            if self._media_kind(e) is not None:
                return str(e.absolute())
        return None

    def _media_kind(self, p: Path) -> str | None:
        """image | video | gif | collection | None (ignored)."""
        if p.is_dir():
            return "collection" if self._collection_count(p) else None
        ext = p.suffix.lower()
        fmts = self.config.get("supported_formats", {})
        if ext == ".gif" or ext in fmts.get("gifs", [".gif"]):
            return "gif"
        if ext in fmts.get("videos", [".mp4", ".avi", ".mkv", ".mov", ".webm"]):
            return "video"
        if ext in IMAGE_EXTENSIONS or ext in fmts.get("images", []):
            return "image"
        return None

    @staticmethod
    def _collection_count(folder: Path) -> int:
        return sum(1 for f in folder.iterdir()
                   if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)

    def _first_collection_image(self, folder: Path) -> Path | None:
        imgs = sorted(f for f in folder.iterdir()
                      if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
        return imgs[0] if imgs else None
