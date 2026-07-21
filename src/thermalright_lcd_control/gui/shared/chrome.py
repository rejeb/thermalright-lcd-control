# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Chrome de fenêtre frameless : redimensionnement par les bords + base QMainWindow.

``EdgeResizeMixin`` fournit curseurs et ``startSystemResize`` sur les bords ;
``FramelessWindow`` l'applique à une QMainWindow sans cadre natif (le
déplacement via ``startSystemMove`` est géré par la titlebar custom).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
)

_RESIZE_MARGIN = 8


class EdgeResizeMixin:
    """Redimensionnement par les bords pour une fenêtre/dialogue frameless."""

    def _edge_at(self, pos):
        r = self.rect()
        m = _RESIZE_MARGIN
        edges = Qt.Edges()
        if pos.x() <= m:
            edges |= Qt.LeftEdge
        if pos.x() >= r.width() - m:
            edges |= Qt.RightEdge
        if pos.y() <= m:
            edges |= Qt.TopEdge
        if pos.y() >= r.height() - m:
            edges |= Qt.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges):
        if (edges & Qt.LeftEdge and edges & Qt.TopEdge) or (edges & Qt.RightEdge and edges & Qt.BottomEdge):
            return Qt.SizeFDiagCursor
        if (edges & Qt.RightEdge and edges & Qt.TopEdge) or (edges & Qt.LeftEdge and edges & Qt.BottomEdge):
            return Qt.SizeBDiagCursor
        if edges & (Qt.LeftEdge | Qt.RightEdge):
            return Qt.SizeHorCursor
        if edges & (Qt.TopEdge | Qt.BottomEdge):
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def mouseMoveEvent(self, e):
        if not self.isMaximized():
            self.setCursor(self._cursor_for(self._edge_at(e.position().toPoint())))
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.isMaximized():
            edges = self._edge_at(e.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None and hasattr(handle, "startSystemResize"):
                    handle.startSystemResize(edges)
                    e.accept()
                    return
        super().mousePressEvent(e)


class FramelessWindow(EdgeResizeMixin, QMainWindow):
    """QMainWindow sans cadre natif, avec poignées de redimensionnement."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMouseTracking(True)

    def toggle_max_restore(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
