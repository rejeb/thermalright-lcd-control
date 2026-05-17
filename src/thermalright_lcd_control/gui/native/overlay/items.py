# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Item texte d'un widget overlay dans la scène preview."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QGraphicsSimpleTextItem

from thermalright_lcd_control.gui.native.overlay import model

_ACCENT = QColor("#e95420")
_HANDLE = 6.0            # côté (px scène) des poignées de redimensionnement


def _qcolor(hexstr: str | None) -> QColor:
    """QColor from a ``#RRGGBB`` or ``#RRGGBBAA`` string.

    Qt parses an 8-hex-digit ``#`` string as ``#AARRGGBB`` (alpha first), which
    swaps red/blue for our ``#RRGGBBAA`` values (``#FF0000FF`` red → blue). Parse
    RGBA explicitly so the preview matches the device render."""
    s = (hexstr or "#FFFFFF").lstrip("#")
    if len(s) >= 8:
        try:
            return QColor(int(s[0:2], 16), int(s[2:4], 16),
                          int(s[4:6], 16), int(s[6:8], 16))
        except ValueError:
            return QColor("#FFFFFF")
    return QColor("#" + s) if s else QColor("#FFFFFF")


class OverlayTextItem(QGraphicsSimpleTextItem):
    """Texte d'un widget (metric / metric_label / clock / label).

    La sélection et le déplacement sont pilotés par :class:`PreviewView` (mêmes
    gestes que l'ancienne UI web) — l'item ne fait que dessiner le texte, le cadre de
    sélection et ses poignées.
    """

    def __init__(self, widget: dict):
        super().__init__()
        self.widget = widget
        self.sel = False
        self.setZValue(10)

    # ── synchronisation modèle → item ─────────────────────────────────────
    def sync(self, live_metrics: dict) -> None:
        # boundingRect() est surchargé (marge poignées) : Qt doit être prévenu
        # avant tout changement pouvant modifier la géométrie (police/texte),
        # sinon l'ancien texte reste visible jusqu'au prochain repaint fortuit.
        self.prepareGeometryChange()
        self.setText(model.widget_text(self.widget, live_metrics))
        self.setFont(model.widget_font(self.widget))
        self.setBrush(QBrush(_qcolor(self.widget.get("color"))))
        self.reposition()
        self.update()

    def reposition(self) -> None:
        """Place l'item pour que l'encre du texte tombe en (fx, fy)."""
        scene = self.scene()
        if scene is None:
            return
        w = scene.sceneRect().width() or 1
        h = scene.sceneRect().height() or 1
        dx, dy = model.ink_offset(self.font())
        self.setPos(self.widget.get("fx", 0.5) * w - dx,
                    self.widget.get("fy", 0.5) * h - dy)

    def store_pos(self) -> None:
        """Recalcule fx/fy depuis la position scène de l'item (après un drag)."""
        scene = self.scene()
        if scene is None:
            return
        w = scene.sceneRect().width() or 1
        h = scene.sceneRect().height() or 1
        dx, dy = model.ink_offset(self.font())
        self.widget["fx"] = max(0.0, min(1.0, (self.pos().x() + dx) / w))
        self.widget["fy"] = max(0.0, min(1.0, (self.pos().y() + dy) / h))

    # ── poignées de redimensionnement ─────────────────────────────────────
    def text_scene_rect(self) -> QRectF:
        """Rect scène de l'encre du texte (sans la marge poignées)."""
        return self.mapToScene(super().boundingRect()).boundingRect()

    # ── rendu ─────────────────────────────────────────────────────────────
    def boundingRect(self) -> QRectF:  # marge pour le cadre + poignées
        return super().boundingRect().adjusted(-_HANDLE, -_HANDLE, _HANDLE, _HANDLE)

    # Le cadre de sélection et les poignées sont dessinés par la vue
    # (drawForeground) : pour un label rigide, le cadre englobe la paire
    # métrique + label, ce qu'un item seul ne peut pas dessiner.

    def set_selected(self, sel: bool) -> None:
        if sel != self.sel:
            self.sel = sel
            self.update()
