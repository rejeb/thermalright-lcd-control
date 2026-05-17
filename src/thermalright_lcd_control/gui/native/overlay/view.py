# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Vue preview : frame LCD + overlays éditables dans une QGraphicsScene.

La scène est en coordonnées device (dev_width × dev_height) ; la vue applique
rotation (0/90/180/270) et zoom d'ajustement — les positions ``fx``/``fy`` et
les tailles de police restent donc en unités device, comme dans l'UI web.

Gestes : clic = sélection, clic sur fond = rubber-band
(Ctrl pour étendre), drag = déplacement du groupe effectif, poignées d'angle =
redimensionnement de la police, clic sans déplacement = ouvre l'inspecteur,
drop depuis la palette = ajout. Escape / Delete sont remontés à l'éditeur.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QRubberBand

from thermalright_lcd_control.gui.native.overlay import model
from thermalright_lcd_control.gui.native.overlay.items import _ACCENT, _HANDLE, OverlayTextItem

MIME_WIDGET = "application/x-trlcd-widget"


class PreviewView(QGraphicsView):
    widget_clicked = Signal(int)            # clic sans déplacement → inspecteur
    group_selection_finished = Signal()     # fin de rubber-band avec 2+ widgets
    selection_changed = Signal()
    widgets_moved = Signal(list)            # ids déplacés (drag terminé)
    widget_resizing = Signal(int)           # font_size en cours de modification
    widget_resized = Signal(int)            # redimensionnement terminé
    widget_dropped = Signal(str, float, float)    # payload JSON {type,key,mode}, fx, fy
    escape_pressed = Signal()
    delete_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform
                            | QPainter.TextAntialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(Qt.black)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.viewport().setMouseTracking(True)   # curseur au survol (resize/move)

        self.rotation = 0
        self._frame_item = QGraphicsPixmapItem()
        self._frame_item.setZValue(0)
        self._frame_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene().addItem(self._frame_item)
        self.scene().setSceneRect(QRectF(0, 0, 320, 240))

        # état partagé avec l'éditeur (mêmes objets)
        self.widgets: list[dict] = []
        self.items_by_id: dict[int, OverlayTextItem] = {}
        self.selected: set[int] = set()

        # gestes en cours
        self._drag = None
        self._resz = None
        self._band = None
        self._rubber = QRubberBand(QRubberBand.Rectangle, self.viewport())

    # ── frame & géométrie ─────────────────────────────────────────────────
    def set_device_size(self, w: int, h: int) -> None:
        self.scene().setSceneRect(QRectF(0, 0, max(1, w), max(1, h)))
        self._refit()
        for item in self.items_by_id.values():
            item.reposition()

    def set_frame(self, pixmap: QPixmap) -> None:
        self._frame_item.setPixmap(pixmap)
        w = self.scene().sceneRect().width()
        if pixmap.width() and abs(pixmap.width() - w) > 0.5:
            self._frame_item.setScale(w / pixmap.width())
        else:
            self._frame_item.setScale(1.0)

    def set_rotation(self, degrees: int) -> None:
        self.rotation = degrees % 360
        self._refit()

    def _refit(self) -> None:
        r = self.scene().sceneRect()
        if r.isEmpty():
            return
        # La rotation ne tourne plus la scène : les médias chargés sont déjà
        # orientés (dossier <h><w>) et les widgets restent droits.
        vp = self.viewport().rect()
        if vp.width() < 2 or vp.height() < 2:
            return
        scale = min(vp.width() / r.width(), vp.height() / r.height())
        t = QTransform()
        t.scale(scale, scale)
        self.setTransform(t)
        self.centerOn(r.center())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._refit()

    def sizeHint(self) -> QSize:
        return QSize(480, 360)

    # ── helpers sélection ─────────────────────────────────────────────────
    def _item_at(self, view_pos: QPoint) -> OverlayTextItem | None:
        for it in self.items(view_pos):
            if isinstance(it, OverlayTextItem):
                return it
        return None

    def set_selection(self, ids) -> None:
        self.selected = set(ids)
        for wid, item in self.items_by_id.items():
            item.set_selected(wid in self.selected)
        self.viewport().update()        # cadre dessiné en drawForeground
        self.selection_changed.emit()

    # ── cadre de sélection (union métrique + label rigide) ────────────────
    def _pair_rect(self, wid) -> QRectF | None:
        """Rect scène de la sélection : l'item, uni à son label/métrique lié
        quand le label n'est pas en floating (paire rigide)."""
        item = self.items_by_id.get(wid)
        if item is None:
            return None
        rect = item.text_scene_rect()
        w = next((x for x in self.widgets if x.get("id") == wid), None)
        partner = None
        if w is not None:
            if w.get("type") == "metric":
                lw = model.label_of(self.widgets, w)
                if lw is not None and not lw.get("floating") and not lw.get("hidden"):
                    partner = self.items_by_id.get(lw.get("id"))
            elif w.get("type") == "metric_label" and not w.get("floating"):
                m = model.metric_of(self.widgets, w)
                if m is not None:
                    partner = self.items_by_id.get(m.get("id"))
        if partner is not None:
            rect = rect.united(partner.text_scene_rect())
        return rect

    def _corner_at(self, wid, scene_pos) -> str | None:
        """Coin ("tl"/"tr"/"bl"/"br") du cadre de sélection sous scene_pos."""
        r = self._pair_rect(wid)
        if r is None:
            return None
        for name, c in (("tl", r.topLeft()), ("tr", r.topRight()),
                        ("bl", r.bottomLeft()), ("br", r.bottomRight())):
            if (QRectF(c.x() - _HANDLE, c.y() - _HANDLE,
                       _HANDLE * 2, _HANDLE * 2).contains(scene_pos)):
                return name
        return None

    def drawForeground(self, painter, rect) -> None:
        super().drawForeground(painter, rect)
        done = set()
        for wid in self.selected:
            r = self._pair_rect(wid)
            if r is None or (r.x(), r.y(), r.width()) in done:
                continue
            done.add((r.x(), r.y(), r.width()))
            pen = QPen(_ACCENT, 0)      # largeur 0 = cosmétique
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r)
            painter.setPen(Qt.NoPen)
            painter.setBrush(_ACCENT)
            half = _HANDLE / 2
            for c in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                painter.drawRect(QRectF(c.x() - half, c.y() - half,
                                        _HANDLE, _HANDLE))

    # ── souris ────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        pos = e.position().toPoint()
        scene_pos = self.mapToScene(pos)

        # poignée d'un item sélectionné → redimensionnement
        for wid in self.selected:
            item = self.items_by_id.get(wid)
            if item is not None and self._corner_at(wid, scene_pos) is not None:
                center = item.mapToScene(item.boundingRect().center())
                d0 = math.hypot(scene_pos.x() - center.x(),
                                scene_pos.y() - center.y()) or 1.0
                self._resz = {"item": item, "center": center, "d0": d0,
                              "f0": model.clamp_font(item.widget.get("font_size", 18))}
                e.accept()
                return

        item = self._item_at(pos)
        if item is not None:
            wid = item.widget["id"]
            if e.modifiers() & Qt.ControlModifier:      # Ctrl-clic : (dé)sélectionne
                sel = set(self.selected)
                sel.symmetric_difference_update({wid})
                self.set_selection(sel)
                e.accept()
                return
            if wid not in self.selected:                # clic sur non-sélectionné → seul
                self.set_selection({wid})
            self._begin_drag(wid, scene_pos)
            e.accept()
            return

        # fond → rubber-band
        base = set(self.selected) if e.modifiers() & Qt.ControlModifier else set()
        self._band = {"origin": pos, "base": base,
                      "add": bool(e.modifiers() & Qt.ControlModifier)}
        self._rubber.setGeometry(QRect(pos, QSize()))
        self._rubber.show()
        e.accept()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        scene_pos = self.mapToScene(pos)
        if self._resz is not None:
            r = self._resz
            d = math.hypot(scene_pos.x() - r["center"].x(),
                           scene_pos.y() - r["center"].y())
            r["item"].widget["font_size"] = model.clamp_font(
                round(r["f0"] * d / r["d0"]))
            self.widget_resizing.emit(r["item"].widget["id"])
            self.viewport().update()    # le cadre (foreground) suit l'item
            e.accept()
            return
        if self._drag is not None:
            self._drag_to(scene_pos)
            e.accept()
            return
        if self._band is not None:
            rect = QRect(self._band["origin"], pos).normalized()
            self._rubber.setGeometry(rect)
            hit = self._widgets_in(rect)
            self.set_selection(self._band["base"] | hit
                               if self._band["add"] else hit)
            e.accept()
            return
        self._update_hover_cursor(pos, scene_pos)
        super().mouseMoveEvent(e)

    def _begin_drag(self, wid, scene_pos) -> None:
        move_ids = model.effective_move_set(self.widgets, self.selected)
        start = {}
        group = None                    # rect englobant des items déplacés
        for mid in move_ids:
            w = next((x for x in self.widgets if x.get("id") == mid), None)
            if w is not None:
                start[mid] = (w.get("fx", 0.5), w.get("fy", 0.5))
            item = self.items_by_id.get(mid)
            if item is not None:
                r = item.text_scene_rect()
                group = r if group is None else group.united(r)
        self._drag = {"id": wid, "origin": scene_pos, "moved": False,
                      "start": start, "rect": group}

    def _drag_to(self, scene_pos) -> None:
        d = self._drag
        rect = self.scene().sceneRect()
        dx = scene_pos.x() - d["origin"].x()
        dy = scene_pos.y() - d["origin"].y()
        # clamp du delta sur le rect englobant du groupe : les éléments d'une
        # paire métrique+label s'arrêtent ensemble au bord, et c'est le texte
        # (pas le point d'ancrage) qui bute sur les bords droit/bas
        g = d["rect"]
        if g is not None:
            dx = max(rect.left() - g.left(), min(rect.right() - g.right(), dx))
            dy = max(rect.top() - g.top(), min(rect.bottom() - g.bottom(), dy))
        dfx = dx / (rect.width() or 1)
        dfy = dy / (rect.height() or 1)
        if abs(dfx) + abs(dfy) > 0.004:
            d["moved"] = True
        for mid, (fx0, fy0) in d["start"].items():
            w = next((x for x in self.widgets if x.get("id") == mid), None)
            item = self.items_by_id.get(mid)
            if w is None:
                continue
            w["fx"] = fx0 + dfx
            w["fy"] = fy0 + dfy
            if item is not None:
                item.reposition()
        self.viewport().update()        # le cadre (foreground) suit les items

    def _update_hover_cursor(self, pos: QPoint, scene_pos) -> None:
        """Curseur contextuel : resize sur les poignées, move sur un widget."""
        for wid in self.selected:
            corner = self._corner_at(wid, scene_pos)
            if corner is not None:
                self.viewport().setCursor(
                    Qt.SizeFDiagCursor if corner in ("tl", "br")
                    else Qt.SizeBDiagCursor)
                return
        if self._item_at(pos) is not None:
            self.viewport().setCursor(Qt.SizeAllCursor)
        else:
            self.viewport().unsetCursor()

    def _widgets_in(self, view_rect: QRect) -> set:
        area = self.mapToScene(view_rect).boundingRect()
        out = set()
        for wid, item in self.items_by_id.items():
            if item.sceneBoundingRect().intersects(area):
                out.add(wid)
        return out

    def mouseReleaseEvent(self, e):
        if self._resz is not None:
            wid = self._resz["item"].widget["id"]
            self._resz = None
            self.widget_resized.emit(wid)
            e.accept()
            return
        if self._drag is not None:
            d, self._drag = self._drag, None
            if d["moved"]:
                self.widgets_moved.emit(sorted(d["start"].keys()))
            else:
                self.widget_clicked.emit(d["id"])
            e.accept()
            return
        if self._band is not None:
            band, self._band = self._band, None
            self._rubber.hide()
            small = (self._rubber.geometry().width()
                     + self._rubber.geometry().height()) < 3
            if small and not band["add"]:
                self.set_selection(set())
            if len(self.selected) >= 2:
                self.group_selection_finished.emit()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    # ── clavier ───────────────────────────────────────────────────────────
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.escape_pressed.emit()
            e.accept()
            return
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected:
            self.delete_pressed.emit()
            e.accept()
            return
        super().keyPressEvent(e)

    # ── drop depuis la palette ────────────────────────────────────────────
    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME_WIDGET):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(MIME_WIDGET):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if not e.mimeData().hasFormat(MIME_WIDGET):
            return super().dropEvent(e)
        payload = bytes(e.mimeData().data(MIME_WIDGET)).decode("utf-8")
        scene_pos = self.mapToScene(e.position().toPoint())
        rect = self.scene().sceneRect()
        fx = max(0.0, min(1.0, scene_pos.x() / (rect.width() or 1)))
        fy = max(0.0, min(1.0, scene_pos.y() / (rect.height() or 1)))
        self.widget_dropped.emit(payload, fx, fy)
        e.acceptProposedAction()
