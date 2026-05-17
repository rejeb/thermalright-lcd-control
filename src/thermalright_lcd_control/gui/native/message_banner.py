# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""In-window dismissible message bar, shown just under the titlebar (same slot
and look as :class:`UpdateBanner`). Used for inline errors/warnings — e.g. a
refused theme overwrite — instead of a modal dialog.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget


class MessageBanner(QWidget):
    """Dismissible bar: « <message> · × ». Hidden until :meth:`show_message`."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("messageBanner")
        # Sans cet attribut, un QWidget nu ne peint pas son background QSS.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 10, 6)
        lay.setSpacing(10)

        self._text = QLabel("")
        self._text.setWordWrap(True)
        self._text.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._text, 1)

        close = QToolButton()
        close.setObjectName("messageClose")
        close.setText("×")
        close.setCursor(Qt.PointingHandCursor)
        close.setToolTip("Dismiss")
        close.clicked.connect(self.hide)
        lay.addWidget(close)

    def show_message(self, text: str) -> None:
        self._text.setText(text)
        self.show()
