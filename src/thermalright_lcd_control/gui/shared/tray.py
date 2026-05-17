# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""System tray + cycle de vie de fermeture de la fenêtre principale.

:class:`TrayWindowMixin` s'ajoute à une ``QMainWindow`` qui expose :

- ``self.backend`` — un :class:`AppBackend` (``cleanup``) ;
- ``self.config`` — le dict de gui_config.yaml (``paths.icon_path``) ;
- ``self.logger`` — un logger.

La fenêtre appelle :meth:`_init_tray_lifecycle` en fin de ``__init__`` ; la
fermeture (croix) cache vers le tray, l'action *Quit* du tray quitte réellement
en sauvegardant les éditions en attente et en arrêtant le controller.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from thermalright_lcd_control.common.logging_config import get_log_file_path


class TrayWindowMixin:
    """Tray + closeEvent « hide to tray » pour une QMainWindow hôte."""

    def _init_tray_lifecycle(self, controller) -> None:
        self._really_quit = False
        self._controller = controller
        self._build_tray()

    # ── system tray ───────────────────────────────────────────────────────
    def _build_tray(self) -> None:
        icon_cfg = self.config.get("paths", {}).get("icon_path")
        icon_path = Path(icon_cfg) if icon_cfg else None
        icon = (QIcon(str(icon_path))
                if icon_path is not None and icon_path.exists()
                else self.windowIcon())
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Thermalright LCD Control")
        menu = QMenu()
        show_action = QAction("Show / Hide", self)
        show_action.triggered.connect(self._toggle_visibility)
        logs_action = QAction("Open Logs", self)
        logs_action.triggered.connect(self._open_logs)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(show_action)
        menu.addAction(logs_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._toggle_visibility()

    def _toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _open_logs(self) -> None:
        """Open the unified log file with the system default application."""
        log_path = Path(get_log_file_path())
        try:
            # Make sure the file exists so the OS handler has something to open.
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch(exist_ok=True)
            self.logger.info(f"Opening log file: {log_path}")
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
            if not opened:
                self.logger.warning(f"No application available to open log file: {log_path}")
        except OSError as e:
            self.logger.error(f"Failed to open log file {log_path}: {e}")

    def _quit_app(self) -> None:
        self.logger.info("Quit requested from tray menu")
        self._really_quit = True
        self.close()

    # ── pause GUI quand la fenêtre n'est pas visible ──────────────────────
    # Cachée (tray) ou minimisée, seule la boucle device doit tourner : la
    # boucle preview et les timers GUI sont coupés, puis relancés au retour.
    def _set_ui_active(self, active: bool) -> None:
        """Hook : les fenêtres l'étendent pour couper leurs propres timers."""
        set_active = getattr(self.backend, "set_preview_active", None)
        if callable(set_active):
            set_active(active)

    def hideEvent(self, event):
        self._set_ui_active(False)
        super().hideEvent(event)

    def showEvent(self, event):
        if not self.isMinimized():
            self._set_ui_active(True)
        super().showEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.isVisible():
            self._set_ui_active(not self.isMinimized())
        super().changeEvent(event)

    # ── fermeture ─────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if not self._really_quit:
            event.ignore()
            self.hide()
            return
        # No auto-save on quit: unsaved edits are discarded (the user saves
        # explicitly via the Save button).
        if self._controller is not None:
            self._controller.stop()
        self.backend.cleanup()
        # setQuitOnLastWindowClosed(False) + the tray icon keep the event loop
        # alive after the window closes, so request the exit explicitly.
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.hide()
        super().closeEvent(event)
        QApplication.quit()
