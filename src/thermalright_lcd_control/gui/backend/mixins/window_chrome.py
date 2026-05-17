# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Suivi d'état de la fenêtre : pause du preview à la disparition.

Mixed into :class:`AppBackend`; reads ``self._window``, ``set_preview_active``
and the ``window_state_changed`` signal from the host. ``eventFilter`` chains to
``QObject.eventFilter`` via the AppBackend MRO.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent


class WindowChromeMixin:
    # ── window integration ────────────────────────────────────────────────
    def set_window(self, window) -> None:
        """Receive the main window for window controls."""
        self._window = window
        # watch state changes (max/restore) without modifying the window
        window.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._window:
            et = event.type()
            if et == QEvent.Type.WindowStateChange:
                self.window_state_changed.emit(bool(self._window.isMaximized()))
                # minimized → no point encoding/pushing invisible frames
                self.set_preview_active(not self._window.isMinimized())
            elif et == QEvent.Type.Show:
                self.set_preview_active(True)
            elif et == QEvent.Type.Hide:
                # window hidden (minimized to tray) → full pause. Unsaved edits
                # are NOT auto-saved: the user decides when to save.
                self.set_preview_active(False)
        return super().eventFilter(watched, event)
