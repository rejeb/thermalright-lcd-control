# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Inspecteur du widget sélectionné (équivalent du panneau ``wconf`` web).

Édition par widget (clock : Date/Time ; metric : label/précision/unité ;
label : texte) + style commun (taille, couleur, police, gras/italique), et
édition groupée quand 2+ widgets sont sélectionnés (valeurs communes, «—» si
mixte). Chaque changement est auto-sauvé (``editor.edit_widget``) ; Cancel
restaure l'état capturé à l'ouverture, la corbeille supprime la sélection.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIntValidator
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.controls import NoScrollComboBox
from thermalright_lcd_control.gui.native.overlay import model
from thermalright_lcd_control.gui.native.toggle_switch import ToggleSwitch

_BACKUP_KEYS = ("mode", "label", "unit", "prec", "text", "font_size", "color",
                "fx", "fy", "font_family", "bold", "italic")

# Inspector title per clock mode (the widget's mode is set by the palette tile).
_CLOCK_TITLES = {"date": "DATE", "time": "TIME", "weekday": "DAY OF WEEK"}


class Stepper(QWidget):
    """Contrôle compact ``-|valeur|+`` (port du ``.wconf-step`` web).

    Contrairement à ``QSpinBox``, il ne s'étire pas dans sa cellule : sa
    largeur reste fixée à son contenu, comme ``.wconf-step`` (inline-flex,
    align-self:flex-start) en CSS.
    """

    def __init__(self, minimum: int, maximum: int, value: int | None,
                 on_change, mixed: bool = False, editable: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("stepper")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._min = minimum
        self._max = maximum
        self._value = value if value is not None else minimum
        self._mixed = mixed
        self._on_change = on_change
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedHeight(34)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        minus = QToolButton()
        minus.setObjectName("stepBtn")
        minus.setText("−")
        minus.clicked.connect(lambda: self._step(-1))

        self._label = QLineEdit("—" if mixed else str(self._value))
        self._label.setObjectName("stepVal")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFixedWidth(34)
        if editable:
            self._label.setValidator(QIntValidator(minimum, maximum, self._label))
            self._label.textEdited.connect(self._apply_text_live)
            self._label.editingFinished.connect(self._commit_text)
        else:
            self._label.setReadOnly(True)
            self._label.setFocusPolicy(Qt.NoFocus)

        plus = QToolButton()
        plus.setObjectName("stepBtn")
        plus.setText("+")
        plus.clicked.connect(lambda: self._step(1))

        lay.addWidget(minus)
        lay.addWidget(self._label)
        lay.addWidget(plus)

    def _apply_text_live(self, text: str) -> None:
        """Applique la valeur au fil de la frappe (sans réécrire le champ,
        pour ne pas déplacer le curseur) ; _commit_text normalisera à la fin."""
        try:
            v = int(text)
        except ValueError:
            return
        v = max(self._min, min(self._max, v))
        if self._mixed or v != self._value:
            self._mixed = False
            self._value = v
            self._on_change(v)

    def _commit_text(self) -> None:
        try:
            v = int(self._label.text())
        except ValueError:
            self._label.setText("—" if self._mixed else str(self._value))
            return
        v = max(self._min, min(self._max, v))
        if self._mixed or v != self._value:
            self._mixed = False
            self._value = v
            self._label.setText(str(v))
            self._on_change(v)

    def _step(self, delta: int) -> None:
        self._mixed = False
        self._value = max(self._min, min(self._max, self._value + delta))
        self._label.setText(str(self._value))
        self._on_change(self._value)

    def setValue(self, value: int) -> None:
        self._mixed = False
        self._value = value
        self._label.setText(str(value))

    def value(self) -> int:
        return self._value


class WidgetInspector(QFrame):
    def __init__(self, editor, backend, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.editor = editor
        self.backend = backend
        self._widget: dict | None = None    # widget en édition simple
        self._group = False
        self._backup: dict | None = None

        editor.open_config_requested.connect(self.open_config)
        editor.open_group_requested.connect(self.open_group_config)
        editor.config_closed.connect(self.close_config)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        head = QHBoxLayout()
        self._title = QLabel("")
        self._title.setObjectName("sectionTitle")
        head.addWidget(self._title)
        head.addStretch(1)
        trash = QToolButton()
        trash.setObjectName("iconBtn")
        trash.setText("🗑")
        trash.setToolTip("Delete widget")
        trash.clicked.connect(self.editor.delete_selected)
        head.addWidget(trash)
        root.addLayout(head)

        self._body = QWidget()
        self._body_lay = QGridLayout(self._body)
        self._body_lay.setContentsMargins(0, 6, 0, 6)
        self._body_lay.setHorizontalSpacing(10)
        root.addWidget(self._body)

        foot = QHBoxLayout()
        foot.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancel_config)
        confirm = QPushButton("Confirm")
        confirm.setObjectName("primary")
        confirm.clicked.connect(self.confirm_config)
        foot.addWidget(cancel)
        foot.addWidget(confirm)
        root.addLayout(foot)

        self.hide()

    # ── ouverture / fermeture ─────────────────────────────────────────────
    def open_config(self, w: dict) -> None:
        self._widget = w
        self._group = False
        self._backup = {k: w.get(k) for k in _BACKUP_KEYS}
        wtype = w.get("type")
        if wtype == "clock":
            self._title.setText(_CLOCK_TITLES.get(w.get("mode"), "CLOCK"))
        elif wtype in ("label", "metric_label", "text"):
            self._title.setText("TEXT")
        else:
            self._title.setText(model.METRIC_NAMES.get(w.get("key"), "Metric"))
        self._rebuild_body()
        self.show()

    def open_group_config(self) -> None:
        self._widget = None
        self._group = True
        self._backup = None
        self._title.setText(f"MULTIPLE — {len(self.editor.view.selected)} widgets")
        self._rebuild_body()
        self.show()

    def close_config(self) -> None:
        self._widget = None
        self._group = False
        self._backup = None
        self.hide()

    def cancel_config(self) -> None:
        w = self._widget
        if w is not None and self._backup is not None:
            w.update(self._backup)
            # les éditions ont été auto-sauvées : repousser l'état restauré
            self.editor.sync_item(w)
            self.editor.push_widget(w)
        self.editor.clear_selection()

    def confirm_config(self) -> None:
        if self._widget is not None:
            self.editor.push_widget(self._widget)
        self.editor.clear_selection()

    # ── construction du corps ─────────────────────────────────────────────
    def _clear_body(self) -> None:
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild_body(self) -> None:
        self._clear_body()
        if self._group:
            self._build_group_body()
        elif self._widget is not None:
            self._build_single_body(self._widget)

    def _add_field(self, row: int, col: int, label: str, control: QWidget) -> None:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        cap = QLabel(label)
        cap.setObjectName("faintText")
        lay.addWidget(cap)
        # Les contrôles à largeur fixe (ex. Stepper) ne doivent pas être
        # étirés sur toute la colonne (cf. align-self:flex-start web).
        fixed_width = control.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
        lay.addWidget(control, 0, Qt.AlignLeft if fixed_width else Qt.Alignment())
        self._body_lay.addWidget(box, row, col)

    @staticmethod
    def _toggle_field(label: str, checked: bool, on_change) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        cap = QLabel(label)
        cap.setObjectName("dimText")
        sw = ToggleSwitch()
        sw.setChecked(checked)
        sw.toggled.connect(on_change)
        lay.addWidget(cap)
        lay.addWidget(sw)
        lay.addStretch(1)
        return box

    def _build_single_body(self, w: dict) -> None:
        row = 0
        if w.get("type") == "clock":
            # The clock mode (date / time / weekday) is fixed by the palette tile
            # it was dropped from — no in-inspector switch. Only styling is edited.
            pass
        elif w.get("type") in ("label", "metric_label", "text"):
            # Standalone text overlay: edit the text; labels are no longer bound
            # to a metric.
            txt = QLineEdit(w.get("text") or "")
            txt.textEdited.connect(lambda v: self._edit(w, "text", v))
            self._add_field(row, 0, "Text", txt)
            row += 1
        else:                                   # metric (value only)
            prec = Stepper(model.PREC_MIN, model.PREC_MAX,
                           model.clamp_prec(w.get("prec", 0)),
                           lambda v: self._edit(w, "prec", v))
            self._add_field(row, 0, "Precision", prec)
            unit = QLineEdit(w.get("unit") or "")
            unit.textEdited.connect(lambda v: self._edit(w, "unit", v))
            self._add_field(row, 1, "Unit", unit)
            row += 1

        # style commun : taille / couleur / police / B-I
        self._size_spin = Stepper(model.FONT_MIN, model.FONT_MAX,
                                   model.clamp_font(w.get("font_size", 18)),
                                   lambda v: self._edit(w, "font_size", v),
                                   editable=True)
        self._add_field(row, 0, "Font size", self._size_spin)
        self._add_field(row, 1, "Color", self._color_btn(
            w.get("color") or "#FFFFFF", lambda c: self._edit(w, "color", c)))
        row += 1
        self._add_field(row, 0, "Font", self._font_combo(
            w.get("font_family"), lambda fam: self._edit(w, "font_family", fam)))
        self._add_field(row, 1, "Style", self._bi_buttons(
            bool(w.get("bold")), bool(w.get("italic")),
            lambda b: self._edit(w, "bold", b), lambda i: self._edit(w, "italic", i)))

    def _build_group_body(self) -> None:
        sel = self.editor.selected_widgets

        def common(prop):
            ws = sel()
            if not ws:
                return None
            v = ws[0].get(prop)
            return v if all(x.get(prop) == v for x in ws) else None

        def apply_all(prop, value):
            for w in sel():
                w[prop] = value
                self.editor.sync_item(w)
                if w.get("type") == "metric":
                    self.editor.propagate_label_style(w)
                self.editor.push_widget(w)

        cs = common("font_size")
        size = Stepper(model.FONT_MIN, model.FONT_MAX,
                       model.clamp_font(cs) if cs is not None else model.FONT_MIN,
                       lambda v: apply_all("font_size", v), mixed=cs is None,
                       editable=True)
        self._add_field(0, 0, "Font size", size)

        cc = common("color")
        self._add_field(0, 1, "Color", self._color_btn(
            cc or "#FFFFFF", lambda c: apply_all("color", c)))

        cf = common("font_family")
        combo = self._font_combo(cf, lambda fam: apply_all("font_family", fam))
        if cf is None and len(sel()) > 1:
            combo.insertItem(0, "—", "__mixed__")
            combo.setCurrentIndex(0)
        self._add_field(1, 0, "Font", combo)

        def tri(prop):
            # tri-état : True = tous, False = aucun, None = partiel ("mixed")
            vals = {bool(w.get(prop)) for w in sel()}
            return vals.pop() if len(vals) == 1 else None

        self._add_field(1, 1, "Style", self._bi_buttons(
            tri("bold"), tri("italic"),
            lambda b: apply_all("bold", b), lambda i: apply_all("italic", i)))

    # ── contrôles réutilisables ───────────────────────────────────────────
    def _color_btn(self, color: str, on_change) -> QPushButton:
        btn = QPushButton()
        btn.setFixedHeight(30)

        def paint(c: str):
            btn.setText(c[:7].upper())
            btn.setStyleSheet(f"background:{c[:7]}; color:#000; border-radius:8px;")

        paint(color)

        def pick():
            c = QColorDialog.getColor(QColor(color[:7]), self, "Widget color")
            if c.isValid():
                hexa = c.name().upper()
                paint(hexa)
                on_change(hexa)

        btn.clicked.connect(pick)
        return btn

    def _font_combo(self, current, on_change) -> QComboBox:
        combo = NoScrollComboBox()
        combo.addItem("Default", "")
        try:
            families = json.loads(self.backend.get_fonts())
        except Exception:
            families = []
        for name in families:
            combo.addItem(name, name)
        idx = combo.findData(current or "")
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _i: (combo.currentData() != "__mixed__"
                        and on_change(combo.currentData() or None)))
        return combo

    def _bi_buttons(self, bold, italic, on_bold, on_italic) -> QWidget:
        """Boutons B/I. ``bold``/``italic`` : True (tous), False (aucun) ou
        None (sélection partielle → style "mixed", un clic active pour tous)."""
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        def make(text, state, on_change, style_font):
            btn = QToolButton()
            btn.setText(text)
            btn.setCheckable(True)
            btn.setObjectName("biBtn")
            style_font(btn)
            btn.setChecked(state is True)
            btn.setProperty("mixed", state is None)

            def toggled(v):
                if btn.property("mixed"):
                    btn.setProperty("mixed", False)
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                on_change(v)

            btn.toggled.connect(toggled)
            return btn

        def bold_font(btn):
            f = btn.font()
            f.setWeight(QFont.Black)
            btn.setFont(f)

        def italic_font(btn):
            f = btn.font()
            f.setItalic(True)
            btn.setFont(f)

        lay.addWidget(make("B", bold, on_bold, bold_font))
        lay.addWidget(make("I", italic, on_italic, italic_font))
        lay.addStretch(1)
        return box

    # ── édition ───────────────────────────────────────────────────────────
    def _edit(self, w: dict, prop: str, value) -> None:
        w[prop] = value
        self.editor.edit_widget(w)

    def _toggle_label(self, metric: dict, on: bool) -> None:
        self.editor.set_label_hidden(metric, not on)
        if on:
            self.editor.propagate_label_style(metric)
        self.open_config(metric)        # re-render : label text + floating

    def _toggle_floating(self, metric: dict, on: bool) -> None:
        lw = model.label_of(self.editor.widgets, metric)
        if lw is None:
            return
        lw["floating"] = on             # conserve la position actuelle
        self.editor.push_widget(lw)

    def _edit_label_text(self, metric: dict, value: str) -> None:
        lw = model.label_of(self.editor.widgets, metric)
        if lw is None:
            return
        lw["text"] = value
        self.editor.sync_item(lw)
        if not lw.get("floating"):
            self.editor.anchor_label_left(metric, lw)
        self.editor.push_widget(lw)

    # ── hooks externes ────────────────────────────────────────────────────
    def sync_size_value(self, w: dict) -> None:
        """MàJ du spinbox taille pendant un redimensionnement à la souris."""
        if self._widget is not None and w.get("id") == self._widget.get("id"):
            spin = getattr(self, "_size_spin", None)
            if spin is not None:
                spin.setValue(model.clamp_font(w.get("font_size", 18)))
