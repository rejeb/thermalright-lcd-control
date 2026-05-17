# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Background library slots: list/select/delete, import and on-demand download.

Mixed into :class:`AppBackend`; reads ``self.preview_manager``,
``self.backgrounds_dir``/``self.backgrounds_base``, ``self.media_endpoint``,
``self.dev_width``/``self.dev_height``, ``self.config``, ``self.devices`` and the
``error_occurred``/``media_added`` signals, and uses the media/thumbnail helpers.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from thermalright_lcd_control.common.media_formats import IMAGE_EXTENSIONS
from thermalright_lcd_control.gui.components import user_backgrounds


class BackgroundMixin:
    def get_backgrounds(self) -> str:
        """JSON: [{name, path, thumbnail, type}] from ``backgrounds_dir``.

        Sort: user-added content (``user_`` files and ``collection_`` folders)
        first, then alphabetical. A freshly imported collection thus shows at the
        top of the grid, not buried among the hundreds of default backgrounds.

        Bundled backgrounds are represented by their PNG thumbnail; the on-demand
        downloaded ``.mp4`` (same base name) is hidden so the same background is
        not shown twice.
        """
        def _is_user(p: Path) -> bool:
            return p.name.startswith("user_") or p.name.startswith("collection_")

        items: list[dict[str, str]] = []
        bg_dir = Path(self.backgrounds_dir)
        if bg_dir.exists():
            # base names of the bundled thumbnails (PNGs shipped with the app):
            # any ``.mp4`` sharing that name is a downloaded bundled background.
            bundled_stems = {p.stem for p in bg_dir.iterdir()
                             if self._is_bundled_background(p)}
            entries = sorted(
                bg_dir.iterdir(),
                key=lambda p: (not _is_user(p), p.name.lower()))
            for entry in entries:
                if ((entry.suffix.lower() == ".mp4"
                        and entry.stem in bundled_stems) or entry.name.lower().startswith("theme_")):
                    continue
                kind = self._media_kind(entry)
                if kind is None:
                    continue
                name = (f"Collection ({self._collection_count(entry)})"
                        if kind == "collection" else entry.stem)
                items.append({
                    "name": name,
                    "path": str(entry.absolute()),
                    "type": kind,
                    "removable": _is_user(entry),
                    "thumbnail": self._thumbnail_for(str(entry)),
                })
        return json.dumps(items)

    def select_background(self, path: str) -> None:
        try:
            path = self._resolve_bundled_background(path)
            self.preview_manager.set_background(path)
            self._publish_live()
        except Exception as e:
            self.logger.error(f"select_background failed: {e}")
            self.error_occurred.emit(f"Background error: {e}")

    def _is_bundled_background(self, p: Path) -> bool:
        """``True`` if ``p`` is a bundled background thumbnail: an image file (a
        PNG shipped with the app) in the resolution folder, excluding user-imported
        content (``user_`` / ``collection_``)."""
        return (p.is_file()
                and p.suffix.lower() in IMAGE_EXTENSIONS
                and not p.name.startswith("user_")
                and not p.name.startswith("collection_")
                and not p.name.startswith("theme_"))

    def _resolve_bundled_background(self, path: str) -> str:
        """Resolve the background to actually show/save.

        - bundled PNG thumbnail (grid selection) → ``.mp4`` of the same name;
        - bundled ``.mp4`` path (referenced by a preset theme) → itself.

        In both cases the real video is downloaded from
        ``{media_endpoint}/bj<width><height>/<name>.mp4`` if it is missing. Any
        other background (user image/video) is returned unchanged.

        If the download fails we fall back to the PNG thumbnail to keep a preview
        and report the error."""
        p = Path(path)

        # Selecting a bundled thumbnail → target the .mp4 of the same name.
        if self._is_bundled_background(p):
            p = p.with_suffix(".mp4")

        # At this point we only download .mp4 files located in the resolution
        # background folder and not imported by the user.
        is_bundled_mp4 = (
            p.suffix.lower() == ".mp4"
            and not p.name.startswith("user_")
            and not p.name.startswith("collection_")
            and not p.name.startswith("theme_")
            and self._same_path(p.parent, self.backgrounds_dir))
        if not is_bundled_mp4 or p.exists():
            return str(p)

        try:
            self._download_bundled_background(p.stem, p)
            return str(p)
        except Exception as e:
            self.logger.error(f"download background {p.stem}.mp4 failed: {e}")
            self.error_occurred.emit(f"Download failed: {e}")
            png = p.with_suffix(".png")
            return str(png) if png.exists() else str(p)

    def _download_bundled_background(self, name: str, dest: Path) -> None:
        """Download ``<name>.mp4`` via the shared helper, using this backend's
        configured ``media_endpoint``."""
        from thermalright_lcd_control.device_controller.display.asset_download import (
            download_bundled_background,
        )
        download_bundled_background(name, dest, media_endpoint=self.media_endpoint)

    def delete_background(self, path: str) -> None:
        """Delete a user-added background (a ``user_`` file or ``collection_``
        folder). Confirms, deletes the themes that use it, and — if the background
        was active — switches the config to the first background + applies before
        removing the files."""
        try:
            p = Path(path).resolve()
            bg_dir = Path(self.backgrounds_dir).resolve()
            if p.parent != bg_dir:
                raise ValueError("target outside the backgrounds folder")
            if not (p.name.startswith("user_") or p.name.startswith("collection_")):
                raise ValueError("default background is not removable")

            def _reset_if_in_use() -> None:
                cur = self.preview_manager.current_background_path
                if cur and self._same_path(cur, p):
                    first = self._first_background(exclude=p)
                    if first:
                        self.preview_manager.set_background(first)
                    self.apply()                # push the new config to the service

            self._delete_media_with_themes(p, "background", _reset_if_in_use)
            # also delete the original + copies for the other resolutions
            user_backgrounds.delete_user_background(
                p.name, self._originals_dir(), Path(self.backgrounds_base))
        except Exception as e:
            self.logger.error(f"delete_background failed: {e}")
            self.error_occurred.emit(f"Delete failed: {e}")

    def _originals_dir(self) -> Path:
        """Originals folder (paths.user_backgrounds)."""
        paths = self.config.get("paths", {})
        return Path(paths.get("user_backgrounds", "./resources/themes/user_backgrounds"))

    def _resolutions(self) -> list[tuple[int, int]]:
        """Distinct resolutions across all configured devices."""
        res = set()
        for d in self.devices:
            try:
                res.add((int(d.get("width", 320)), int(d.get("height", 240))))
            except (TypeError, ValueError):
                continue
        if not res:
            res.add((self.dev_width, self.dev_height))
        return sorted(res)

    def open_file_dialog(self) -> None:
        """Open a native QFileDialog, import the files, emit ``media_added``.

        - 1 file  → copied into ``backgrounds_dir`` prefixed ``user_``
        - N files → ``collection_{uuid8}/`` folder containing all the files
        """
        paths, _ = QFileDialog.getOpenFileNames(
            self._window, "Add media", str(Path(self.backgrounds_dir).absolute()),
            "Media (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.avi *.mkv *.mov *.webm)")
        if not paths:
            return
        try:
            dest = self._import_media([Path(p) for p in paths])
            kind = self._media_kind(dest) or "image"
            self.media_added.emit(json.dumps({"path": str(dest.absolute()), "type": kind}))
        except Exception as e:
            self.logger.error(f"add media failed: {e}")
            self.error_occurred.emit(f"Add media failed: {e}")

    def _import_media(self, paths: list[Path]) -> Path:
        """Store the original in user_backgrounds then materialize a resized copy
        for each configured device resolution. Returns the active-resolution copy
        (for the grid). Video > 5 s → MediaTooLongError."""
        original = user_backgrounds.import_originals(paths, self._originals_dir())
        user_backgrounds.materialize_all(
            self._originals_dir(), Path(self.backgrounds_base), self._resolutions())
        # path of the active copy to return for the grid
        active = Path(self.backgrounds_dir)
        hits = list(active.glob(original.stem + ".*")) or [active / original.stem]
        return hits[0]
