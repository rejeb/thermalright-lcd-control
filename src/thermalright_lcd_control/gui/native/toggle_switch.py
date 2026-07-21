# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Interrupteur à glissière (cf. ``.switch`` de l'UI web) — remplace les
``QCheckBox`` nus, dont le rendu (case à cocher) ne correspond pas au style
« sliding switch » du web. Peint au ``QPainter`` (piste + bouton coulissant
animé) car QSS ne permet pas de sous-contrôle ``::after`` pour le bouton."""

from __future__ import annotations

import weakref

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton

_ON_COLOR = QColor("#e95420")
_OFF_COLOR = QColor("#454545")
_instances: weakref.WeakSet[ToggleSwitch] = weakref.WeakSet()


def set_theme_colors(on: str, off: str) -> None:
    """Appelé depuis ``apply_ui_theme`` pour suivre le thème actif."""
    global _ON_COLOR, _OFF_COLOR
    _ON_COLOR, _OFF_COLOR = QColor(on), QColor(off)
    for sw in list(_instances):
        sw.update()


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(38, 22)
        self._knob = 19.0 if self.isChecked() else 3.0
        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        # Clic utilisateur → passe par le ``toggled`` Qt (setChecked() interne
        # à QAbstractButton n'est pas virtuel, un override Python ne
        # l'intercepterait pas).
        self.toggled.connect(self._animate_to)
        _instances.add(self)

    def setChecked(self, checked: bool) -> None:
        # Sync programmatique (souvent avec signaux bloqués, ex. resynchro
        # silencieuse depuis le backend) : ``toggled`` ne serait alors jamais
        # émis, laissant le bouton visuellement figé du mauvais côté malgré
        # l'état correct. On repositionne donc aussi ici, explicitement.
        super().setChecked(checked)
        self._animate_to(checked)

    def _animate_to(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(19.0 if checked else 3.0)
        self._anim.start()

    def get_knob_pos(self) -> float:
        return self._knob

    def set_knob_pos(self, value: float) -> None:
        self._knob = value
        self.update()

    knobPos = Property(float, get_knob_pos, set_knob_pos)

    def sizeHint(self):
        return self.size()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(_ON_COLOR if self.isChecked() else _OFF_COLOR)
        p.drawRoundedRect(rect, radius, radius)
        knob_d = rect.height() - 6
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(self._knob, 3, knob_d, knob_d))
        p.end()
