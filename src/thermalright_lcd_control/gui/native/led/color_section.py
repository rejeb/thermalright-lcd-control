# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Colour section: global colour swatch + brightness + presets + on/off."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

_PRESETS = [
    (255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0),
    (0, 255, 255), (0, 0, 255), (255, 0, 255), (255, 255, 255),
]


class ColorSection(QWidget):
    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._settings = None
        self._build_ui()

    def _build_ui(self):
        box = QGroupBox("Colour", self)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        lay = QVBoxLayout(box)

        top = QHBoxLayout()
        self._swatch = QPushButton(self)
        self._swatch.setFixedSize(64, 32)
        self._swatch.setCursor(Qt.PointingHandCursor)
        self._swatch.clicked.connect(self._pick_color)
        top.addWidget(QLabel("Colour:", self))
        top.addWidget(self._swatch)
        top.addStretch(1)
        self._on_btn = QPushButton("On", self)
        self._off_btn = QPushButton("Off", self)
        self._on_btn.clicked.connect(lambda: self._set_global_on(True))
        self._off_btn.clicked.connect(lambda: self._set_global_on(False))
        top.addWidget(self._on_btn)
        top.addWidget(self._off_btn)
        lay.addLayout(top)

        bright = QHBoxLayout()
        bright.addWidget(QLabel("Brightness:", self))
        self._brightness = QSlider(Qt.Horizontal, self)
        self._brightness.setRange(0, 100)
        self._brightness.valueChanged.connect(self._on_brightness)
        self._bright_label = QLabel("65%", self)
        bright.addWidget(self._brightness, 1)
        bright.addWidget(self._bright_label)
        lay.addLayout(bright)

        presets = QGroupBox("Presets", self)
        grid = QGridLayout(presets)
        grid.setSpacing(4)
        for i, (r, g, b) in enumerate(_PRESETS):
            btn = QPushButton(self)
            btn.setFixedSize(34, 24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"background: rgb({r},{g},{b}); border:1px solid #333;")
            btn.clicked.connect(lambda _=False, c=(r, g, b): self.set_color(*c))
            grid.addWidget(btn, i // 4, i % 4)
        lay.addWidget(presets)

    # ── data binding ──────────────────────────────────────────────────
    def load_settings(self, settings):
        self._settings = settings
        self._paint_swatch(settings.color)
        self._brightness.blockSignals(True)
        self._brightness.setValue(settings.brightness)
        self._brightness.blockSignals(False)
        self._bright_label.setText(f"{settings.brightness}%")

    def _paint_swatch(self, color):
        r, g, b = color
        self._swatch.setStyleSheet(
            f"background: rgb({r},{g},{b}); border:1px solid #333; border-radius:6px;")

    # ── dispatch ──────────────────────────────────────────────────────
    def set_color(self, r, g, b):
        self._settings.color = (r, g, b)
        self._paint_swatch((r, g, b))
        self._on_change(self._settings)

    def set_brightness(self, pct):
        self._settings.brightness = pct
        self._on_change(self._settings)

    def _pick_color(self):
        if self._settings is None:
            return
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(QColor(*self._settings.color), self, "LED colour")
        if c.isValid():
            self.set_color(c.red(), c.green(), c.blue())

    def _on_brightness(self, v):
        self._bright_label.setText(f"{v}%")
        if self._settings is not None:
            self.set_brightness(v)

    def _set_global_on(self, on):
        if self._settings is not None:
            self._settings.global_on = on
            self._on_change(self._settings)
