# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Advanced section: sensor sources + diagnostic test mode."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class AdvancedSection(QWidget):
    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._settings = None
        self._build_ui()

    def _build_ui(self):
        box = QGroupBox("Advanced", self)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        form = QFormLayout(box)

        self._temp_cpu = QRadioButton("CPU", self)
        self._temp_gpu = QRadioButton("GPU", self)
        tg = QButtonGroup(self)
        tg.setExclusive(True)
        tg.addButton(self._temp_cpu)
        tg.addButton(self._temp_gpu)
        self._temp_cpu.toggled.connect(
            lambda c: c and self.set_temp_source("cpu"))
        self._temp_gpu.toggled.connect(
            lambda c: c and self.set_temp_source("gpu"))
        trow = QHBoxLayout()
        trow.addWidget(self._temp_cpu)
        trow.addWidget(self._temp_gpu)
        trow.addStretch(1)
        form.addRow("Temperature follows:", trow)

        self._load_cpu = QRadioButton("CPU", self)
        self._load_gpu = QRadioButton("GPU", self)
        lg = QButtonGroup(self)
        lg.setExclusive(True)
        lg.addButton(self._load_cpu)
        lg.addButton(self._load_gpu)
        self._load_cpu.toggled.connect(
            lambda c: c and self.set_load_source("cpu"))
        self._load_gpu.toggled.connect(
            lambda c: c and self.set_load_source("gpu"))
        lrow = QHBoxLayout()
        lrow.addWidget(self._load_cpu)
        lrow.addWidget(self._load_gpu)
        lrow.addStretch(1)
        form.addRow("Load follows:", lrow)

        self._test = QCheckBox("Test mode (cycle 4 reference colours)", self)
        self._test.toggled.connect(self.set_test_mode)
        form.addRow(self._test)

    def load_settings(self, settings):
        self._settings = settings
        for w in (self._temp_cpu, self._temp_gpu, self._load_cpu,
                  self._load_gpu, self._test):
            w.blockSignals(True)
        (self._temp_cpu if settings.temp_source == "cpu"
         else self._temp_gpu).setChecked(True)
        (self._load_cpu if settings.load_source == "cpu"
         else self._load_gpu).setChecked(True)
        self._test.setChecked(settings.test_mode)
        for w in (self._temp_cpu, self._temp_gpu, self._load_cpu,
                  self._load_gpu, self._test):
            w.blockSignals(False)

    def set_temp_source(self, source):
        self._settings.temp_source = source
        self._on_change(self._settings)

    def set_load_source(self, source):
        self._settings.load_source = source
        self._on_change(self._settings)

    def set_test_mode(self, on):
        self._settings.test_mode = on
        self._on_change(self._settings)
