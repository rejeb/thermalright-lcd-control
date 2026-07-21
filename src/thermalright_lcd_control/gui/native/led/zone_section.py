# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Zone section: per-zone colour, brightness and on/off; carousel toggle."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ZoneSection(QWidget):
    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._settings = None
        self._rows = []
        self._box = QGroupBox("Zones", self)
        self._zones_lay = QVBoxLayout(self._box)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._box)

        carousel = QHBoxLayout()
        self._sync = QCheckBox("Zone-sync carousel", self)
        self._sync.toggled.connect(self._on_sync)
        self._interval = QSpinBox(self)
        self._interval.setRange(1, 600)
        self._interval.setSuffix(" ticks")
        self._interval.valueChanged.connect(self._on_interval)
        carousel.addWidget(self._sync)
        carousel.addStretch(1)
        carousel.addWidget(QLabel("Interval:", self))
        carousel.addWidget(self._interval)
        self._zones_lay.addLayout(carousel)

    def load_settings(self, settings):
        self._settings = settings
        self._rebuild(settings.zones)
        self._sync.blockSignals(True)
        self._sync.setChecked(settings.zone_sync)
        self._sync.blockSignals(False)
        self._interval.blockSignals(True)
        self._interval.setValue(settings.zone_sync_interval_ticks)
        self._interval.blockSignals(False)

    def _rebuild(self, zones):
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        for i, zone in enumerate(zones):
            self._rows.append(self._make_row(i, zone))

    def _make_row(self, i, zone):
        row = QWidget(self)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(f"Zone {i + 1}", row))
        lay.addStretch(1)
        swatch = QPushButton(row)
        swatch.setFixedSize(48, 22)
        swatch.setCursor(Qt.PointingHandCursor)
        r, g, b = zone.color
        swatch.setStyleSheet(f"background: rgb({r},{g},{b}); border:1px solid #333;")
        swatch.clicked.connect(lambda _=False, idx=i, sw=swatch: self._pick(idx, sw))
        bright = QSpinBox(row)
        bright.setRange(0, 100)
        bright.setSuffix("%")
        bright.setValue(zone.brightness)
        bright.valueChanged.connect(lambda v, idx=i: self.set_zone_brightness(idx, v))
        enabled = QCheckBox("On", row)
        enabled.setChecked(zone.on)
        enabled.toggled.connect(lambda on, idx=i: self.set_zone_on(idx, on))
        lay.addWidget(swatch)
        lay.addWidget(bright)
        lay.addWidget(enabled)
        self._zones_lay.addWidget(row)
        return row

    # ── dispatch ──────────────────────────────────────────────────────
    def set_zone_color(self, i, r, g, b):
        self._settings.zones[i].color = (r, g, b)
        self._on_change(self._settings)

    def set_zone_brightness(self, i, pct):
        self._settings.zones[i].brightness = pct
        self._on_change(self._settings)

    def set_zone_on(self, i, on):
        self._settings.zones[i].on = on
        self._on_change(self._settings)

    def _pick(self, i, swatch):
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(*self._settings.zones[i].color)
        c = QColorDialog.getColor(cur, self, f"Zone {i + 1} colour")
        if c.isValid():
            swatch.setStyleSheet(
                f"background: rgb({c.red()},{c.green()},{c.blue()}); border:1px solid #333;")
            self.set_zone_color(i, c.red(), c.green(), c.blue())

    def _on_sync(self, on):
        if self._settings is not None:
            self._settings.zone_sync = on
            self._on_change(self._settings)

    def _on_interval(self, v):
        if self._settings is not None:
            self._settings.zone_sync_interval_ticks = v
            self._on_change(self._settings)
