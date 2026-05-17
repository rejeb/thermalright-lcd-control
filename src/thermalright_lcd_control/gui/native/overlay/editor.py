# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Coordinateur de l'éditeur d'overlays : état des widgets + backend + vue.

Porte la logique overlay de l'ancienne UI web : construction des items, ajout depuis la
palette (avec création automatique du label séparé d'une métrique), propagation
du style métrique → label, ensembles de déplacement rigides, suppression, et
synchronisation complète vers ``AppBackend`` (add/update/delete_widget).
"""

from __future__ import annotations

import json

from PySide6.QtCore import QObject, QTimer, Signal

from thermalright_lcd_control.gui.native.overlay import model
from thermalright_lcd_control.gui.native.overlay.items import OverlayTextItem
from thermalright_lcd_control.gui.native.overlay.view import PreviewView

_LIVE_INTERVAL_MS = 1000    # rafraîchissement des valeurs metric/clock


class OverlayEditor(QObject):
    # Signal(object) et non Signal(dict) : dict serait converti en QVariantMap
    # (copie) — l'inspecteur muterait la copie et le preview ne verrait rien.
    open_config_requested = Signal(object)  # widget → l'inspecteur s'ouvre
    open_group_requested = Signal()         # 2+ widgets sélectionnés
    config_closed = Signal()                # sélection vidée → fermer l'inspecteur

    def __init__(self, backend, view: PreviewView, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.view = view
        self.widgets: list[dict] = []
        view.widgets = self.widgets           # objets partagés avec la vue
        self.live_metrics: dict = {}

        view.widget_clicked.connect(self._on_widget_clicked)
        view.group_selection_finished.connect(self._maybe_open_group)
        view.widgets_moved.connect(self._on_moved)
        view.widget_resizing.connect(self._on_resizing)
        view.widget_resized.connect(self._on_resized)
        view.widget_dropped.connect(self._on_dropped)
        view.escape_pressed.connect(self.clear_selection)
        view.delete_pressed.connect(self.delete_selected)

        self.backend.widgets_loaded.connect(self.load_widgets)

        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._refresh_live)
        self._live_timer.start(_LIVE_INTERVAL_MS)

    # ── (re)construction depuis le backend ────────────────────────────────
    def load_widgets(self, payload: str) -> None:
        try:
            widgets = json.loads(payload)
        except Exception:
            widgets = []
        self.widgets.clear()
        self.widgets.extend(widgets)
        self.view.set_selection(set())
        self.config_closed.emit()
        self.rebuild()

    def rebuild(self) -> None:
        """(Re)crée tous les items de la scène depuis ``self.widgets``."""
        for item in self.view.items_by_id.values():
            self.view.scene().removeItem(item)
        self.view.items_by_id.clear()
        for w in self.widgets:
            if w.get("type") == "metric_label" and w.get("hidden"):
                continue
            item = OverlayTextItem(w)
            self.view.scene().addItem(item)
            self.view.items_by_id[w["id"]] = item
            item.sync(self.live_metrics)
        self.view.set_selection(self.view.selected & set(self.view.items_by_id))

    def find(self, wid) -> dict | None:
        return next((w for w in self.widgets if w.get("id") == wid), None)

    def sync_item(self, w: dict) -> None:
        item = self.view.items_by_id.get(w.get("id"))
        if item is not None:
            item.sync(self.live_metrics)
            # Filet de sécurité : force un repaint même si la propagation
            # scène→vue rate la mise à jour de l'item.
            self.view.viewport().update()

    # ── édition (inspecteur) ──────────────────────────────────────────────
    def edit_widget(self, w: dict) -> None:
        """MàJ preview + live-publish vers le backend (sans sauvegarde fichier)."""
        self.sync_item(w)
        if w.get("type") == "metric":
            self.propagate_label_style(w)
        self.push_widget(w)

    def propagate_label_style(self, metric: dict) -> None:
        lw = model.label_of(self.widgets, metric)
        if lw is None:
            return
        lw["font_size"] = metric.get("font_size")
        lw["color"] = metric.get("color")
        lw["font_family"] = metric.get("font_family")
        lw["bold"] = bool(metric.get("bold"))
        lw["italic"] = bool(metric.get("italic"))
        self.sync_item(lw)
        if not lw.get("floating"):
            self.anchor_label_left(metric, lw)
        self.push_widget(lw)

    def anchor_label_left(self, metric: dict, lw: dict) -> None:
        """Place le label juste à gauche de la valeur (même ligne).

        Les largeurs sont celles de l'encre du texte (pas la boîte gonflée par
        les poignées de sélection). Près d'un bord c'est la paire entière
        [label · valeur] qui glisse pour rester visible : le label ne s'écrase
        jamais sur la valeur et la valeur ne sort pas de l'écran."""
        label_item = self.view.items_by_id.get(lw.get("id"))
        metric_item = self.view.items_by_id.get(metric.get("id"))
        if label_item is None or metric_item is None:
            return
        sw = self.view.scene().sceneRect().width() or 1
        label_w = label_item.text_scene_rect().width() / sw
        value_w = metric_item.text_scene_rect().width() / sw
        gap = 6.0 / sw

        fx = metric.get("fx", 0.5)
        fx = min(fx, max(0.0, 1.0 - value_w))       # la valeur tient à droite
        fx = max(fx, min(1.0, label_w + gap))       # le label tient à gauche
        if fx != metric.get("fx"):
            metric["fx"] = fx
            metric_item.reposition()
            self.push_widget(metric)
        lw["fx"] = max(0.0, fx - label_w - gap)
        lw["fy"] = metric.get("fy", 0.5)
        label_item.reposition()

    def set_label_hidden(self, metric: dict, hidden: bool) -> dict | None:
        """Toggle « Show label » ; crée le label au premier affichage."""
        lw = model.label_of(self.widgets, metric)
        if not hidden and lw is None:
            return self.add_metric_label(metric)
        if lw is None:
            return None
        lw["hidden"] = hidden
        self.rebuild()
        if not hidden:
            self.propagate_label_style(metric)
        self.backend.update_widget(json.dumps({"id": lw["id"], "hidden": hidden}))
        return lw

    # ── ajout ─────────────────────────────────────────────────────────────
    def _on_dropped(self, payload: str, fx: float, fy: float) -> None:
        try:
            spec = json.loads(payload)
        except Exception:
            return
        self.add_widget(spec.get("type", ""), spec.get("key"),
                        spec.get("mode"), fx, fy)

    def add_widget(self, wtype: str, key, mode, fx: float, fy: float) -> None:
        w = {**model.DEFAULT_STYLE, "fx": fx, "fy": fy}
        if wtype == "clock":
            w.update({"type": "clock", "mode": mode or "time"})
        elif wtype in ("text", "label"):
            # Standalone text overlay (label / title) — independent of any metric.
            w.update({"type": "text", "text": "Text"})
        else:
            m = model.METRICS.get(key, {})
            w.update({"type": "metric", "key": key, "label": "",
                      "unit": m.get("unit", ""), "prec": m.get("prec", 0)})
        w["id"] = self._backend_add(w)
        self.widgets.append(w)
        self.rebuild()
        self.view.set_selection({w["id"]})
        self.open_config_requested.emit(w)

    def add_metric_label(self, metric: dict) -> dict:
        lw = model.label_of(self.widgets, metric)
        if lw is not None:
            return lw
        m = model.METRICS.get(metric.get("key"), {})
        lw = {"type": "metric_label", "group": metric.get("group"),
              "text": m.get("label", "Label"),
              "font_size": metric.get("font_size", 18),
              "color": metric.get("color", "#FFFFFF"),
              "font_family": metric.get("font_family"),
              "bold": bool(metric.get("bold")), "italic": bool(metric.get("italic")),
              "floating": False, "hidden": False,
              "fx": metric.get("fx", 0.5), "fy": metric.get("fy", 0.5)}
        lw["id"] = self._backend_add(lw)
        self.widgets.append(lw)
        self.rebuild()
        self.anchor_label_left(metric, lw)      # → à gauche de la valeur
        self.backend.update_widget(json.dumps(
            {"id": lw["id"], "fx": lw["fx"], "fy": lw["fy"]}))
        return lw

    def _backend_add(self, w: dict) -> int:
        res = json.loads(self.backend.add_widget(json.dumps(w)))
        return res.get("id")

    # ── suppression / sélection ───────────────────────────────────────────
    def delete_selected(self) -> None:
        if not self.view.selected:
            return
        ids = set()
        for wid in self.view.selected:
            w = self.find(wid)
            if w is None:
                continue
            ids.add(wid)
            if w.get("type") == "metric":
                lw = model.label_of(self.widgets, w)
                if lw:
                    ids.add(lw["id"])
        self.widgets[:] = [w for w in self.widgets if w.get("id") not in ids]
        self.view.set_selection(set())
        self.config_closed.emit()
        self.rebuild()
        for wid in ids:
            self.backend.delete_widget(wid)

    def clear_selection(self) -> None:
        self.view.set_selection(set())
        self.config_closed.emit()

    def selected_widgets(self) -> list[dict]:
        return [w for w in self.widgets if w.get("id") in self.view.selected]

    # ── réactions à la vue ────────────────────────────────────────────────
    def _on_widget_clicked(self, wid: int) -> None:
        w = self.find(wid)
        if w is None:
            return
        # label de métrique : pas d'inspecteur propre → toujours rediriger vers
        # la fenêtre de la métrique. Rigide : la sélection porte sur la paire
        # (via la métrique) ; floating : le label reste sélectionné pour être
        # déplaçable indépendamment.
        if w.get("type") == "metric_label":
            m = model.metric_of(self.widgets, w)
            if m is not None:
                self.view.set_selection({wid if w.get("floating") else m["id"]})
                self.open_config_requested.emit(m)
                return
        self.view.set_selection({wid})
        self.open_config_requested.emit(w)

    def _maybe_open_group(self) -> None:
        if len(self.view.selected) >= 2:
            self.open_group_requested.emit()

    def _on_moved(self, ids: list) -> None:
        for wid in ids:
            item = self.view.items_by_id.get(wid)
            w = self.find(wid)
            if item is None or w is None:
                continue
            self.backend.update_widget(json.dumps(
                {"id": wid, "fx": w.get("fx"), "fy": w.get("fy")}))

    def _on_resizing(self, wid: int) -> None:
        w = self.find(wid)
        if w is not None:
            self.sync_item(w)

    def _on_resized(self, wid: int) -> None:
        w = self.find(wid)
        if w is not None:
            self.edit_widget(w)

    # ── synchronisation backend ───────────────────────────────────────────
    def push_widget(self, w: dict) -> None:
        """Envoie l'état complet d'un widget au backend."""
        self.backend.update_widget(json.dumps({
            "id": w.get("id"), "type": w.get("type"), "key": w.get("key"),
            "mode": w.get("mode"), "group": w.get("group"),
            "label": w.get("label"), "unit": w.get("unit"), "prec": w.get("prec"),
            "text": w.get("text"),
            "font_size": w.get("font_size"), "color": w.get("color"),
            "font_family": w.get("font_family"),
            "bold": bool(w.get("bold")), "italic": bool(w.get("italic")),
            "fx": w.get("fx"), "fy": w.get("fy"),
            "hidden": bool(w.get("hidden")), "floating": bool(w.get("floating")),
        }))

    # ── valeurs live ──────────────────────────────────────────────────────
    def set_live_updates(self, active: bool) -> None:
        """Fenêtre cachée/minimisée → stoppe le rafraîchissement 1 Hz des
        valeurs metric/clock (sondes CPU/GPU comprises)."""
        if active:
            if not self._live_timer.isActive():
                self._refresh_live()            # valeurs à jour immédiatement
                self._live_timer.start(_LIVE_INTERVAL_MS)
        else:
            self._live_timer.stop()

    def _refresh_live(self) -> None:
        try:
            # Les None sont conservés : une sonde indisponible doit s'afficher
            # « -- » dans le preview (le device ne rend pas ces widgets).
            self.live_metrics.update(json.loads(self.backend.get_metrics()))
        except Exception:
            pass
        for w in self.widgets:
            if w.get("type") in ("metric", "clock"):
                self.sync_item(w)
