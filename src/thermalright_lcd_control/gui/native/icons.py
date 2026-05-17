# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Icônes vectorielles des boutons de fenêtre (min/max/restore/close).

Dessinées au ``QPainter`` (traits fins, cf. les SVG ``.wbtn`` de l'UI web) au
lieu de glyphes Unicode : plus fiable / cohérent d'un système à l'autre que des
caractères comme « ❐ » dont le rendu dépend de la police installée.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_SIZE = 16
_STROKE = 1.3


def _canvas() -> tuple[QPixmap, QPainter]:
    pm = QPixmap(_SIZE, _SIZE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def _pen(color: QColor) -> QPen:
    pen = QPen(color)
    pen.setWidthF(_STROKE)
    pen.setCapStyle(Qt.RoundCap)
    return pen


def _draw_square(p: QPainter, rect: QRectF, radius: float = 1.6) -> None:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    p.drawPath(path)


def window_icon(kind: str, color: QColor) -> QIcon:
    pm, p = _canvas()
    p.setPen(_pen(color))
    if kind == "min":
        y = _SIZE / 2
        p.drawLine(int(_SIZE * 0.25), int(y), int(_SIZE * 0.75), int(y))
    elif kind == "max":
        _draw_square(p, QRectF(_SIZE * 0.22, _SIZE * 0.22, _SIZE * 0.56, _SIZE * 0.56))
    elif kind == "restore":
        _draw_square(p, QRectF(_SIZE * 0.18, _SIZE * 0.34, _SIZE * 0.48, _SIZE * 0.48))
        _draw_square(p, QRectF(_SIZE * 0.34, _SIZE * 0.18, _SIZE * 0.48, _SIZE * 0.48))
    elif kind == "close":
        a, b = _SIZE * 0.28, _SIZE * 0.72
        p.drawLine(int(a), int(a), int(b), int(b))
        p.drawLine(int(b), int(a), int(a), int(b))
    elif kind == "save":
        # disquette : contour, languette haute, volet bas
        s = _SIZE
        _draw_square(p, QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), radius=1.4)
        p.drawRect(QRectF(s * 0.34, s * 0.2, s * 0.32, s * 0.16))   # languette
        p.drawRect(QRectF(s * 0.32, s * 0.5, s * 0.36, s * 0.3))    # volet
    elif kind == "export":
        # flèche vers le haut sortant d'un bac ouvert
        s = s2 = _SIZE
        cx = s2 * 0.5
        p.drawLine(int(cx), int(s * 0.66), int(cx), int(s * 0.22))          # tige
        p.drawLine(int(s * 0.32), int(s * 0.42), int(cx), int(s * 0.22))    # tête ↖
        p.drawLine(int(s * 0.68), int(s * 0.42), int(cx), int(s * 0.22))    # tête ↗
        p.drawLine(int(s * 0.26), int(s * 0.56), int(s * 0.26), int(s * 0.8))
        p.drawLine(int(s * 0.26), int(s * 0.8), int(s * 0.74), int(s * 0.8))
        p.drawLine(int(s * 0.74), int(s * 0.8), int(s * 0.74), int(s * 0.56))
    p.end()
    return QIcon(pm)
