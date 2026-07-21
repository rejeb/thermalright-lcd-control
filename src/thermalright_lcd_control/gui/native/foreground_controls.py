# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Contrôles Foreground : activation + opacité.

L'état réel est piloté par le backend : le signal ``theme_loaded`` renvoie
``fg_enabled``/``fg_opacity``/``fg_path`` et resynchronise l'UI. Réactiver le
toggle resélectionne le dernier foreground connu.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.toggle_switch import ToggleSwitch


class ForegroundControls(QFrame):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.backend = backend
        self._last_path = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        head = QHBoxLayout()
        title = QLabel("Foreground")
        title.setObjectName("sectionTitle")
        self._toggle = ToggleSwitch()
        self._toggle.setToolTip("Enable / disable foreground")
        self._toggle.clicked.connect(self._on_toggle)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self._toggle)
        lay.addLayout(head)

        self._row = QWidget()
        row = QHBoxLayout(self._row)
        row.setContentsMargins(0, 6, 0, 0)
        cap = QLabel("Opacity")
        cap.setObjectName("dimText")
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(50)
        self._slider.valueChanged.connect(self._on_slider)
        self._spin = QSpinBox()
        self._spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._spin.setRange(0, 100)
        self._spin.setSuffix("%")
        self._spin.setValue(50)
        self._spin.valueChanged.connect(self._on_spin)
        row.addWidget(cap)
        row.addWidget(self._slider, 1)
        row.addWidget(self._spin)
        lay.addWidget(self._row)

        self.backend.theme_loaded.connect(self._sync_from_theme)

    # ── état piloté par le backend ────────────────────────────────────────
    def _sync_from_theme(self, payload: str) -> None:
        try:
            info = json.loads(payload)
        except Exception:
            return
        opacity = info.get("fg_opacity")
        pct = round((opacity if opacity is not None else 0.5) * 100)
        for w in (self._slider, self._spin):
            w.blockSignals(True)
            w.setValue(int(pct))
            w.blockSignals(False)
        if info.get("fg_path"):
            self._last_path = info["fg_path"]   # mémorise pour réactivation
        enabled = bool(info.get("fg_enabled"))
        self._toggle.blockSignals(True)
        self._toggle.setChecked(enabled)
        self._toggle.blockSignals(False)
        self._row.setVisible(enabled)

    # ── interactions ──────────────────────────────────────────────────────
    def _on_toggle(self, on: bool) -> None:
        if on:
            if self._last_path:
                self.backend.select_foreground(self._last_path)
            else:                       # aucun foreground mémorisé à réactiver
                self._toggle.setChecked(False)
        else:
            self.backend.clear_foreground()
        # le backend émet theme_loaded → _sync_from_theme fait foi

    def _on_slider(self, value: int) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(value)
        self._spin.blockSignals(False)
        self.backend.set_foreground_opacity(value / 100.0)

    def _on_spin(self, value: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        self.backend.set_foreground_opacity(value / 100.0)
