# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Mode section: pick one of the six LED animation modes."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.device_controller.led.led_models import LEDMode

_LABELS = [
    (LEDMode.STATIC, "Static"),
    (LEDMode.BREATHING, "Breathing"),
    (LEDMode.COLORFUL, "Colourful"),
    (LEDMode.RAINBOW, "Rainbow"),
    (LEDMode.TEMP_LINKED, "Temperature-linked"),
    (LEDMode.LOAD_LINKED, "Load-linked"),
]


class ModeSection(QWidget):
    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._settings = None
        self._radios = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._build_ui()

    def _build_ui(self):
        box = QGroupBox("Mode", self)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        lay = QVBoxLayout(box)
        for mode, label in _LABELS:
            rb = QRadioButton(label, self)
            rb.toggled.connect(lambda checked, m=mode: checked and self.set_mode(m))
            self._radios[mode] = rb
            self._group.addButton(rb)
            lay.addWidget(rb)

    def load_settings(self, settings):
        self._settings = settings
        rb = self._radios.get(settings.mode)
        if rb is not None:
            rb.blockSignals(True)
            rb.setChecked(True)
            rb.blockSignals(False)

    def set_mode(self, mode):
        self._settings.mode = mode
        self._on_change(self._settings)
