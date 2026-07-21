# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Preview overlay controls: rotation and foreground opacity.

Mixed into :class:`AppBackend`; updates ``self.current_rotation`` and the
``PreviewManager``, then republishes the live frame.
"""
from __future__ import annotations


class OverlayStyleMixin:
    def set_rotation(self, degrees: int) -> None:
        """Set the rotation (0/90/180/270) and update the PreviewManager."""
        old_w, old_h = self._media_res()
        self.current_rotation = degrees % 360
        self.preview_manager.set_rotation(self.current_rotation)
        new_w, new_h = self._media_res()
        if (new_w, new_h) != (old_w, old_h):
            self._remap_media_resolution(f"{old_w}{old_h}", f"{new_w}{new_h}")
        self._sync_rotation_dirs()
        # Rotation updates the live preview / engine only (no disk write): like
        # every other edit, the user persists it explicitly via Apply/Save.
        self._publish_live()
        self._emit_theme_loaded()

    def _remap_media_resolution(self, old: str, new: str) -> None:
        """Bascule la sélection courante (fond/premier plan, potentiellement non
        sauvée) vers le dossier de la nouvelle orientation — même règle que le
        placeholder ``{resolution}`` de ConfigLoader, mais appliquée à l'état
        mémoire pour ne pas perdre la sélection au reload."""
        pm = self.preview_manager
        bg = pm.current_background_path
        if bg and f"/{old}/" in str(bg):
            pm.set_background(str(bg).replace(f"/{old}/", f"/{new}/"))
        fg = pm.current_foreground_path
        if fg and f"/{old}/" in str(fg):
            pm.set_foreground(str(fg).replace(f"/{old}/", f"/{new}/"))

    def set_foreground_opacity(self, value: float) -> None:
        """Foreground opacity, 0.0–1.0."""
        value = max(0.0, min(1.0, value))
        self.preview_manager.set_foreground_opacity(value)
        self._publish_live()
