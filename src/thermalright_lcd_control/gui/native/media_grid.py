# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Grille de vignettes (thèmes / backgrounds / foregrounds).

Grilles de vignettes (thèmes / backgrounds / foregrounds) : cartes
avec vignette + légende, bouton de suppression sur les items ``removable``,
sélection exclusive au clic.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.icons import window_icon
from thermalright_lcd_control.gui.shared.pixmaps import pixmap_from_data_url

_CARD_W, _CARD_H = 172, 152
_PIC_W, _PIC_H = 160, 120


class _Card(QWidget):
    def __init__(self, grid: MediaGrid, item: dict):
        super().__init__()
        self.item = item
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(3)
        pic = QLabel()
        pic.setFixedSize(_PIC_W, _PIC_H)
        pic.setAlignment(Qt.AlignCenter)
        pm = pixmap_from_data_url(item.get("thumbnail") or "")
        if not pm.isNull():
            pic.setPixmap(pm.scaled(_PIC_W, _PIC_H, Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation))
        lay.addWidget(pic)
        cap = QLabel(item.get("name") or "")
        cap.setObjectName("dimText")
        cap.setAlignment(Qt.AlignCenter)
        cap.setMaximumWidth(_PIC_W)
        lay.addWidget(cap)

        self._del_btn = None
        if item.get("removable"):
            btn = QToolButton(pic)
            btn.setObjectName("thumbDel")
            btn.setIcon(window_icon("close", QColor("#ffffff")))
            btn.setIconSize(QSize(12, 12))
            btn.setToolTip("Delete")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(22, 22)
            btn.move(_PIC_W - 27, 5)
            btn.hide()
            btn.clicked.connect(lambda: grid.item_deleted.emit(self.item))
            self._del_btn = btn

    def enterEvent(self, e) -> None:
        if self._del_btn is not None:
            self._del_btn.show()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        if self._del_btn is not None:
            self._del_btn.hide()
        super().leaveEvent(e)


class MediaGrid(QListWidget):
    item_selected = Signal(dict)
    item_deleted = Signal(dict)

    def __init__(self, parent=None, sticky_selection: bool = True):
        super().__init__(parent)
        # ``sticky_selection=False`` (themes grid): a click applies the item but
        # leaves no persistent highlight — clicking is an action, not a selection.
        self._sticky_selection = sticky_selection
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListWidget.SingleSelection if sticky_selection
                              else QListWidget.NoSelection)
        self.itemClicked.connect(self._on_clicked)
        self._empty_msg = "Nothing here yet."

    def set_items(self, items: list[dict], empty_msg: str = "Nothing here yet.",
                  select_first: bool = False, select_index: int | None = None) -> None:
        self._empty_msg = empty_msg
        self.clear()
        if not items:
            hint = QListWidgetItem(empty_msg)
            hint.setFlags(Qt.NoItemFlags)
            self.addItem(hint)
            return
        for data in items:
            entry = QListWidgetItem()
            entry.setSizeHint(QSize(_CARD_W, _CARD_H))
            entry.setData(Qt.UserRole, data)
            self.addItem(entry)
            self.setItemWidget(entry, _Card(self, data))
        if not self._sticky_selection:
            return                       # actions grid: never pre-select an item
        if select_index is not None and 0 <= select_index < len(items):
            self.setCurrentRow(select_index)
        elif select_first:
            self.setCurrentRow(0)

    def _on_clicked(self, entry: QListWidgetItem) -> None:
        data = entry.data(Qt.UserRole)
        if data:
            self.item_selected.emit(data)
