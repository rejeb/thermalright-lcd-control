# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""In-window « a new version is available » banner + its background checker.

:class:`UpdateChecker` runs :func:`common.update_check.check_for_update` on a
daemon thread and emits ``update_available`` (queued to the GUI thread by
PySide) when a newer release exists. :class:`UpdateBanner` is the dismissible
bar shown in response; hidden by default, it never appears when the check finds
nothing or fails.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from thermalright_lcd_control.common.update_check import (
    RELEASES_URL,
    check_for_update,
)


class UpdateChecker(QObject):
    """Best-effort startup update check on a background thread."""

    update_available = Signal(str)      # latest version string

    def __init__(self, timeout: float = 3.0, parent: QObject | None = None):
        super().__init__(parent)
        self._timeout = timeout

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            latest = check_for_update(timeout=self._timeout)
        except Exception:
            print("Failed to get new version")
            latest = None      # silent: never surface a failed check
        if latest:
            self.update_available.emit(latest)


class UpdateBanner(QWidget):
    """Dismissible bar: « A new version (X) is available · Download · × »."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("updateBanner")
        # Sans cet attribut, un QWidget nu ne peint pas son background QSS.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 10, 6)
        lay.setSpacing(10)

        lay.addStretch(1)

        self._text = QLabel("")
        lay.addWidget(self._text)

        link = QLabel(f'<a href="{RELEASES_URL}">Download</a>')
        link.setObjectName("updateLink")
        link.setOpenExternalLinks(False)
        link.linkActivated.connect(self._open_releases)
        lay.addWidget(link)

        lay.addStretch(1)

        close = QToolButton()
        close.setObjectName("updateClose")
        close.setText("×")
        close.setCursor(Qt.PointingHandCursor)
        close.setToolTip("Dismiss")
        close.clicked.connect(self.hide)
        lay.addWidget(close)

    def show_update(self, version: str) -> None:
        self._text.setText(f"A new version ({version}) is available")
        self.show()

    def _open_releases(self, *_) -> None:
        QDesktopServices.openUrl(QUrl(RELEASES_URL))
