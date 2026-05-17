# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Petits contrôles partagés de l'UI native."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox


class NoScrollComboBox(QComboBox):
    """QComboBox qui ignore la molette : évite de changer la valeur par
    accident en scrollant un formulaire (comme un <select> web fermé)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, e):
        e.ignore()
