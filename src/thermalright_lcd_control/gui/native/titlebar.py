# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Barre de titre custom de l'UI native (fenêtre frameless).

Logo + nom, un onglet par device — l'onglet actif porte ✎ (edit) et, pour un
device ajouté par l'utilisateur, 🗑 (delete) — bouton add device, toggle
light/dark et les pastilles min/max/close. (Les boutons de sauvegarde thème /
config sont dans la ligne méta du PreviewPanel.)
Le déplacement de la fenêtre passe par ``startSystemMove``, le double-clic
bascule maximize/restore.

Les actions device (add/edit/delete) sont émises en signaux : les dialogues
sont la responsabilité de la fenêtre principale.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTabBar,
    QToolButton,
    QWidget,
)

from thermalright_lcd_control.gui.native.icons import window_icon


class TitleBar(QWidget):
    add_device_requested = Signal()
    edit_device_requested = Signal()
    delete_device_requested = Signal()
    ui_theme_changed = Signal(str)      # 'light' | 'dark'

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setObjectName("titlebar")
        self.setFixedHeight(52)
        self.setAttribute(Qt.WA_StyledBackground, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 12, 0)
        lay.setSpacing(12)

        # logo + nom
        self._logo = QLabel()
        self._logo.setFixedSize(24, 24)
        self._logo.setScaledContents(True)
        icon_path = self.backend.config.get("paths", {}).get("icon_path", "")
        icon_pm = QPixmap(icon_path) if icon_path else QPixmap()
        if not icon_pm.isNull():
            self._logo.setPixmap(icon_pm)
        else:
            self._logo.setText("🖵")
            self._logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._logo)
        self._name = QLabel("Thermalright LCD Control")
        self._name.setObjectName("appName")
        lay.addWidget(self._name)

        # devices : un onglet par device ; l'onglet actif porte le bouton ✎
        self.device_tabs = QTabBar()
        self.device_tabs.setObjectName("deviceTabs")
        self.device_tabs.setExpanding(False)
        self.device_tabs.setUsesScrollButtons(True)
        self.device_tabs.setDrawBase(False)
        self.device_tabs.setFocusPolicy(Qt.NoFocus)
        self.device_tabs.currentChanged.connect(self._on_device_selected)
        lay.addWidget(self.device_tabs)
        # Boutons portés par l'onglet ACTIF : ✎ toujours, 🗑 seulement pour un
        # device ajouté par l'utilisateur (jamais pour un device auto-détecté).
        self._tab_edit_btn = QToolButton()
        self._tab_edit_btn.setObjectName("tabEditBtn")
        self._tab_edit_btn.setText("✎")
        self._tab_edit_btn.setToolTip("Edit this device")
        self._tab_edit_btn.setFocusPolicy(Qt.NoFocus)
        self._tab_edit_btn.clicked.connect(self.edit_device_requested.emit)
        self._tab_del_btn = QToolButton()
        self._tab_del_btn.setObjectName("tabDelBtn")
        self._tab_del_btn.setText("🗑")
        self._tab_del_btn.setToolTip("Delete this device")
        self._tab_del_btn.setFocusPolicy(Qt.NoFocus)
        self._tab_del_btn.clicked.connect(self.delete_device_requested.emit)
        self._tab_btns = QWidget()
        btns_lay = QHBoxLayout(self._tab_btns)
        btns_lay.setContentsMargins(0, 0, 0, 0)
        btns_lay.setSpacing(2)
        btns_lay.addWidget(self._tab_edit_btn)
        btns_lay.addWidget(self._tab_del_btn)
        self._edit_btn_index: int = -1     # tab currently holding the buttons

        add_btn = QToolButton()
        add_btn.setObjectName("iconBtn")
        add_btn.setText("+")
        add_btn.setToolTip("Add a device")
        add_btn.clicked.connect(self.add_device_requested.emit)
        lay.addWidget(add_btn)

        lay.addStretch(1)

        # toggle light/dark
        self._theme_btn = QToolButton()
        self._theme_btn.setObjectName("iconBtn")
        self._theme_btn.setToolTip("Toggle light / dark theme")
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._sync_theme_glyph()
        lay.addWidget(self._theme_btn)

        # Les boutons « Save theme » / « Save config » vivent désormais dans la
        # ligne méta du PreviewPanel (à droite de « Live Preview · w,h »).

        # min / max / close
        self._icon_color = QColor(160, 160, 160)
        self._maximized = False
        self._min_btn = self._win_btn("min", "Minimize", self._minimize)
        self._max_btn = self._win_btn("max", "Maximize", self._toggle_max)
        self._close_btn = self._win_btn("close", "Close", lambda: self.window().close())
        self._close_btn.setObjectName("winBtnClose")
        for b in (self._min_btn, self._max_btn, self._close_btn):
            lay.addWidget(b)

        self.backend.window_state_changed.connect(self._sync_max_glyph)
        self.backend.devices_refreshed.connect(self.reload_devices)
        self.reload_devices()

    # ── devices ───────────────────────────────────────────────────────────
    def reload_devices(self) -> None:
        """(Re)peuple les onglets depuis le backend, sans ré-émettre select."""
        tabs = self.device_tabs
        tabs.blockSignals(True)
        self._detach_edit_btn()
        while tabs.count():
            tabs.removeTab(0)
        try:
            devices = json.loads(self.backend.get_devices())
        except Exception:
            devices = []
        for d in devices:
            idx = tabs.addTab(d.get("label", "—"))
            tabs.setTabData(idx, d)
            if d.get("current"):
                tabs.setCurrentIndex(idx)
        if not devices:
            idx = tabs.addTab("—")
            tabs.setTabData(idx, None)
            tabs.setTabEnabled(idx, False)
        tabs.blockSignals(False)
        self._place_edit_btn()

    def _detach_edit_btn(self) -> None:
        if self._edit_btn_index >= 0:
            self.device_tabs.setTabButton(self._edit_btn_index, QTabBar.RightSide, None)
            # setTabButton(None) reparente et cache l'ancien widget : on le garde
            self._tab_btns.setParent(self)
            self._tab_btns.hide()
            self._edit_btn_index = -1

    def _place_edit_btn(self) -> None:
        """Pose ✎ (+ 🗑 si device utilisateur) sur l'onglet ACTIF uniquement
        (jamais sur le placeholder). Les devices auto-détectés n'ont pas de 🗑."""
        idx = self.device_tabs.currentIndex()
        d = self.device_tabs.tabData(idx) if idx >= 0 else None
        if d is None:
            return
        self._tab_del_btn.setVisible(not d.get("auto"))
        self.device_tabs.setTabButton(idx, QTabBar.RightSide, self._tab_btns)
        self._tab_btns.show()
        self._edit_btn_index = idx

    def current_device_key(self) -> str | None:
        d = self.device_tabs.tabData(self.device_tabs.currentIndex())
        return d.get("key") if d else None

    def current_device_id(self) -> str | None:
        d = self.device_tabs.tabData(self.device_tabs.currentIndex())
        return d.get("id") if d else None

    def _on_device_selected(self, _index: int) -> None:
        self._detach_edit_btn()
        self._place_edit_btn()
        key = self.current_device_key()
        if key:
            self.backend.select_device(key)

    # ── thème UI ──────────────────────────────────────────────────────────
    def _toggle_theme(self) -> None:
        mode = "light" if self.backend.get_ui_theme() == "dark" else "dark"
        self.backend.set_ui_theme(mode)
        self._sync_theme_glyph()
        self.ui_theme_changed.emit(mode)

    def _sync_theme_glyph(self) -> None:
        # icône du mode *courant* (soleil = light, lune = dark)
        self._theme_btn.setText("☾" if self.backend.get_ui_theme() == "dark" else "☀")

    # ── contrôles fenêtre ─────────────────────────────────────────────────
    def _win_btn(self, kind: str, tip: str, slot) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("winBtn")
        btn.setProperty("iconKind", kind)
        btn.setIconSize(QSize(10, 10))
        btn.setIcon(window_icon(kind, self._icon_color))
        btn.setToolTip(tip)
        btn.clicked.connect(slot)
        return btn

    def set_icon_color(self, color: QColor) -> None:
        """Régénère les icônes min/max/close dans la couleur du thème actif."""
        self._icon_color = color
        for btn in (self._min_btn, self._max_btn, self._close_btn):
            btn.setIcon(window_icon(btn.property("iconKind"), color))

    def _minimize(self) -> None:
        self.window().showMinimized()

    def _toggle_max(self) -> None:
        self.window().toggle_max_restore()

    def _sync_max_glyph(self, maximized: bool) -> None:
        self._maximized = maximized
        self._max_btn.setProperty("iconKind", "restore" if maximized else "max")
        self._max_btn.setIcon(window_icon("restore" if maximized else "max", self._icon_color))
        self._max_btn.setToolTip("Restore" if maximized else "Maximize")

    # ── drag de la fenêtre ────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.childAt(e.position().toPoint()) in (None, self._logo, self._name):
            handle = self.window().windowHandle()
            if handle is not None and hasattr(handle, "startSystemMove"):
                handle.startSystemMove()
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton and self.childAt(e.position().toPoint()) is None:
            self._toggle_max()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)
