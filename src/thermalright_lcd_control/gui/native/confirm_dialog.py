# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Dialogue de confirmation frameless (remplace QMessageBox.question).

QMessageBox est décoré par le serveur (barre de titre GTK/KDE de la distro) ;
ce dialogue reprend le chrome custom du DeviceDialog pour un rendu identique
sur toutes les distributions.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.icons import window_icon
from thermalright_lcd_control.gui.native.theme import tokens


class ConfirmDialog(QDialog):
    """``exec()`` retourne ``QDialog.Accepted`` si l'action est confirmée."""

    def __init__(self, owner, title: str, message: str, *,
                 confirm_label: str = "Delete", ui_theme: str = "dark",
                 destructive: bool = True, icon_path: str = ""):
        # Même choix que DeviceDialog : pas de transient parent (GNOME
        # attacherait le dialogue à la fenêtre principale) + modalité
        # application, et remise au premier plan si la fenêtre principale
        # est réactivée par le compositeur.
        super().__init__(None)
        self.setWindowModality(Qt.ApplicationModal)
        if owner is not None:
            owner.window().installEventFilter(self)

        self.setWindowTitle(title)
        self.setObjectName("deviceDialog")      # réutilise le fond/bordure QSS
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)     # laisse la bordure QSS visible
        root.setSpacing(0)
        # Le dialogue épouse exactement le contenu (plus de hauteur en trop).
        root.setSizeConstraint(QLayout.SetFixedSize)

        header = QWidget()
        header.setObjectName("titlebar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header.setFixedHeight(48)
        head_lay = QHBoxLayout(header)
        head_lay.setContentsMargins(16, 0, 12, 0)
        head_lay.setSpacing(10)
        # Logo de l'application (même chargement que la barre de titre) ; repli sur
        # un glyphe si l'icône est absente.
        logo = QLabel()
        logo.setFixedSize(20, 20)
        logo.setScaledContents(True)
        icon_pm = QPixmap(icon_path) if icon_path else QPixmap()
        if not icon_pm.isNull():
            logo.setPixmap(icon_pm)
        else:
            logo.setText("🖵")
            logo.setAlignment(Qt.AlignCenter)
        head_lay.addWidget(logo)
        head_title = QLabel(title)
        head_title.setObjectName("appName")
        head_lay.addWidget(head_title)
        head_lay.addStretch(1)
        close_btn = QToolButton()
        close_btn.setObjectName("winBtnClose")
        close_btn.setIconSize(QSize(10, 10))
        close_btn.setIcon(window_icon("close", QColor(tokens(ui_theme)["dim"])))
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.reject)
        head_lay.addWidget(close_btn)
        self._drag_pos = None
        header.mousePressEvent = self._drag_press
        header.mouseMoveEvent = self._drag_move
        header.mouseReleaseEvent = self._drag_release
        root.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(16)
        text = QLabel(message)
        text.setWordWrap(True)
        text.setMinimumWidth(388)               # ~420px de large une fois les marges
        text.setStyleSheet("font-size: 15px; font-weight: 600;")
        body.addWidget(text)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        confirm = QPushButton(confirm_label)
        confirm.setObjectName("danger" if destructive else "primary")
        confirm.clicked.connect(self.accept)
        btn_row.addWidget(confirm)
        body.addLayout(btn_row)
        root.addLayout(body)

        cancel.setDefault(True)
        cancel.setFocus()

    # ── focus : cf. DeviceDialog (pas de transient parent) ─────────────────
    def eventFilter(self, obj, e):
        if e.type() == QEvent.WindowActivate and self.isVisible():
            QTimer.singleShot(0, self._bring_to_front)
        return super().eventFilter(obj, e)

    def _bring_to_front(self) -> None:
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    # ── drag du header : move manuel, cf. DeviceDialog ─────────────────────
    def _drag_press(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _drag_move(self, e) -> None:
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def _drag_release(self, _e) -> None:
        self._drag_pos = None
