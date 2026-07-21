# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Panneau droit : onglets Themes / Backgrounds / Foregrounds / Overlay widgets.

Chaque onglet média est une :class:`MediaGrid` alimentée par les slots JSON du
backend (get_themes / get_backgrounds / get_foregrounds) et rafraîchie par les
signaux ``themes_refreshed`` / ``media_added`` / ``foreground_added``. Le
dernier onglet héberge la palette de widgets overlay.
"""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.media_grid import MediaGrid
from thermalright_lcd_control.gui.native.overlay.palette import WidgetPalette


class SideTabs(QTabWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend

        # Themes
        self.themes_grid = MediaGrid(sticky_selection=False)
        # Clicking a theme loads it into the live preview only (no disk write);
        # the user persists it explicitly via the Apply/Save buttons.
        self.themes_grid.item_selected.connect(
            lambda it: self.backend.select_theme(it.get("yaml_path", "")))
        self.themes_grid.item_deleted.connect(
            lambda it: self.backend.delete_theme(it.get("yaml_path", "")))
        refresh = QPushButton("⟳ Refresh")
        refresh.clicked.connect(self.load_themes)
        self.addTab(self._pane("Available themes", self.themes_grid, refresh),
                    "Themes")

        # Backgrounds
        self.bg_grid = MediaGrid()
        self.bg_grid.item_selected.connect(
            lambda it: self.backend.select_background(it.get("path", "")))
        self.bg_grid.item_deleted.connect(self._delete_background)
        add_media = QPushButton("+ Add media")
        add_media.clicked.connect(self.backend.open_file_dialog)
        self.addTab(self._pane("Backgrounds", self.bg_grid, add_media),
                    "Backgrounds")

        # Foregrounds
        self.fg_grid = MediaGrid()
        self.fg_grid.item_selected.connect(
            lambda it: self.backend.select_foreground(it.get("path", "")))
        self.fg_grid.item_deleted.connect(self._delete_foreground)
        add_fg = QPushButton("+ Add foreground")
        add_fg.clicked.connect(self.backend.add_foreground)
        clear_fg = QPushButton("Clear")
        clear_fg.clicked.connect(self.backend.clear_foreground)
        self.addTab(self._pane("Foregrounds", self.fg_grid, add_fg, clear_fg),
                    "Foregrounds")

        # Overlay widgets (palette)
        self.palette = WidgetPalette()
        self.addTab(self.palette, "Overlay widgets")

        self.backend.themes_refreshed.connect(self.load_themes)
        self.backend.media_added.connect(lambda _payload=None: self.load_backgrounds())
        self.backend.foreground_added.connect(self.load_foregrounds)

    @staticmethod
    def _pane(title: str, grid: MediaGrid, *actions: QWidget) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 8, 0, 0)
        head = QHBoxLayout()
        cap = QLabel(title)
        cap.setObjectName("sectionTitle")
        head.addWidget(cap)
        head.addStretch(1)
        for a in actions:
            head.addWidget(a)
        lay.addLayout(head)
        lay.addWidget(grid, 1)
        return pane

    # ── chargement ────────────────────────────────────────────────────────
    def _json(self, payload: str) -> list:
        try:
            return json.loads(payload)
        except Exception:
            return []

    def load_themes(self, select_name: str | None = None) -> list:
        themes = self._json(self.backend.get_themes())
        idx = next((i for i, t in enumerate(themes)
                    if t.get("name") == select_name), 0) if select_name else 0
        self.themes_grid.set_items(themes, "No themes found.",
                                   select_first=bool(themes), select_index=idx)
        return themes

    def load_backgrounds(self) -> None:
        self.bg_grid.set_items(self._json(self.backend.get_backgrounds()),
                               "No backgrounds found.")

    def load_foregrounds(self) -> None:
        self.fg_grid.set_items(self._json(self.backend.get_foregrounds()),
                               "No foregrounds found.")

    def load_all(self) -> list:
        themes = self.load_themes()
        self.load_backgrounds()
        self.load_foregrounds()
        return themes

    # ── suppressions (confirmation native côté backend) ──────────────────
    def _delete_background(self, item: dict) -> None:
        self.backend.delete_background(item.get("path", ""))
        self.load_backgrounds()

    def _delete_foreground(self, item: dict) -> None:
        self.backend.delete_foreground(item.get("path", ""))
        self.load_foregrounds()
