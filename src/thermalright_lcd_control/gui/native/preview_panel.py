# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Panneau preview : vue LCD (frames PIL → QPixmap), rotation et méta-infos."""

from __future__ import annotations

import json

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.icons import window_icon
from thermalright_lcd_control.gui.native.overlay.view import PreviewView
from thermalright_lcd_control.gui.shared.pixmaps import pixmap_from_vips

_SHADOW_BLUR, _SHADOW_DY = 28, 8    # cf. l'ancien QGraphicsDropShadowEffect


class PreviewPanel(QWidget):
    rotation_changed = Signal(int)
    device_size_changed = Signal(int, int)
    save_config_requested = Signal()        # "save config" (save icon)
    save_theme_requested = Signal(str)      # "save theme" (export icon + name)

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.rotation = 0
        self.device_w = 320
        self.device_h = 240
        self._empty = True

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # cadre LCD (cf. .lcd/.lcd-screen web) : bezel autour de l'écran
        self.view = PreviewView()
        self._lcd_frame = QFrame()
        self._lcd_frame.setObjectName("lcdFrame")
        frame_lay = QVBoxLayout(self._lcd_frame)
        frame_lay.setContentsMargins(8, 8, 8, 8)
        frame_lay.addWidget(self.view)
        # Ombre du bezel peinte par paintEvent (pré-rendue et mise en cache) :
        # QGraphicsDropShadowEffect re-rendait bezel + vidéo en logiciel avec
        # un flou gaussien à chaque frame du preview (~26 % de CPU mesuré).
        self._shadow_pm: QPixmap | None = None
        self._shadow_geom = None
        lay.addWidget(self._lcd_frame, 0, Qt.AlignHCenter)

        # ligne méta (cf. .preview-meta web) : ● Live Preview · [w, h]
        lay.setSpacing(12)                      # .preview-wrap { gap:12px }
        meta = QHBoxLayout()
        meta.setSpacing(8)                      # .preview-meta { gap:8px }
        dot = QLabel("●")
        dot.setObjectName("liveDot")
        live = QLabel("Live Preview")
        live.setObjectName("liveText")
        sep = QLabel("·")
        sep.setObjectName("metaSep")
        self._res = QLabel("—")
        self._res.setObjectName("resPill")
        meta.addStretch(1)
        meta.addWidget(dot)
        meta.addWidget(live)
        meta.addWidget(sep)
        meta.addWidget(self._res)
        meta.addStretch(1)

        # À droite de « Live Preview · w,h », de gauche à droite :
        #  1) sauvegarde de la config active (icône save),
        #  2) sauvegarde du thème : champ nom avec l'icône export INTÉGRÉE au champ
        #     (action interne, pas un bouton séparé).
        self._save_config_btn = QToolButton()
        self._save_config_btn.setObjectName("iconBtn")
        self._save_config_btn.setIcon(window_icon("save", QColor(160, 160, 160)))
        self._save_config_btn.setIconSize(QSize(16, 16))
        self._save_config_btn.setToolTip("Save config")
        self._save_config_btn.setCursor(Qt.PointingHandCursor)
        self._save_config_btn.clicked.connect(self.save_config_requested.emit)
        meta.addWidget(self._save_config_btn)
        # Le bouton passe en ambre tant qu'il y a des édits non sauvegardés, pour
        # inciter l'utilisateur à sauver la config.
        self.backend.unsaved_changes_changed.connect(self._on_unsaved_changed)

        self._theme_name = QLineEdit()
        self._theme_name.setObjectName("themeNameField")
        self._theme_name.setPlaceholderText("Theme name")
        self._theme_name.setFixedWidth(160)
        self._theme_name.setClearButtonEnabled(True)
        self._theme_name.returnPressed.connect(self._emit_save_theme)
        # « Save theme » = action intégrée au champ (icône export, côté gauche).
        self._save_theme_action = QAction(
            window_icon("export", QColor(160, 160, 160)), "Save theme", self)
        self._save_theme_action.setToolTip("Save theme")
        self._save_theme_action.triggered.connect(self._emit_save_theme)
        self._theme_name.addAction(self._save_theme_action, QLineEdit.LeadingPosition)
        # Les boutons internes du QLineEdit (action export + clear) sont des
        # QToolButton : curseur main pour montrer qu'ils sont cliquables.
        for b in self._theme_name.findChildren(QToolButton):
            b.setCursor(Qt.PointingHandCursor)
        meta.addWidget(self._theme_name)
        lay.addLayout(meta)

        # ligne rotation : radios 0/90/180/270 sur une ligne, juste sous
        # "Live Preview" (remplace l'ancien bouton rotation flottant).
        rot = QHBoxLayout()
        rot.setSpacing(14)
        rot.addStretch(1)
        self._rot_group = QButtonGroup(self)
        self._rot_buttons: dict[int, QRadioButton] = {}
        for deg in (0, 90, 180, 270):
            rb = QRadioButton(f"{deg}°")
            rb.setObjectName("rotateRadio")
            rb.setCursor(Qt.PointingHandCursor)
            rb.setChecked(deg == 0)
            self._rot_group.addButton(rb, deg)
            self._rot_buttons[deg] = rb
            rot.addWidget(rb)
        rot.addStretch(1)
        self._rot_group.idClicked.connect(self._on_rotate_pick)
        lay.addLayout(rot)

        self.backend.frame_ready_pil.connect(self._on_frame)
        self.backend.theme_loaded.connect(self._on_theme_loaded)

    # ── save ──────────────────────────────────────────────────────────────
    _SAVE_IDLE = QColor(160, 160, 160)
    _SAVE_DIRTY = QColor(232, 165, 71)      # ambre : édits non sauvegardés

    def _on_unsaved_changed(self, dirty: bool) -> None:
        """Recolore les icônes « Save config » et « Save theme » selon l'état
        non-sauvegardé (ambre = édits à sauver)."""
        color = self._SAVE_DIRTY if dirty else self._SAVE_IDLE
        self._save_config_btn.setIcon(window_icon("save", color))
        self._save_config_btn.setToolTip(
            "Save config — unsaved changes" if dirty else "Save config")
        self._save_theme_action.setIcon(window_icon("export", color))
        self._save_theme_action.setToolTip(
            "Save theme — unsaved changes" if dirty else "Save theme")

    def _emit_save_theme(self) -> None:
        self.save_theme_requested.emit(self._theme_name.text())

    def clear_theme_name(self) -> None:
        self._theme_name.clear()

    # ── device / thème ────────────────────────────────────────────────────
    def reload_device_info(self) -> None:
        try:
            info = json.loads(self.backend.get_device_info())
        except Exception:
            info = {}
        w, h = int(info.get("width") or 320), int(info.get("height") or 240)
        self._res.setText(f"w: {w}, h: {h}")
        self.device_w, self.device_h = w, h
        self.view.set_device_size(w, h)
        self.device_size_changed.emit(w, h)

    def set_target_box(self, sw: int, sh: int) -> None:
        """Contraint la taille de la vue au format calculé par le layout responsive."""
        self.view.setFixedSize(max(1, sw), max(1, sh))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._shadow_pm = None

    def paintEvent(self, e):
        g = self._lcd_frame.geometry()
        if g.width() > 1:
            if self._shadow_pm is None or self._shadow_geom != g:
                self._shadow_pm = self._render_shadow(g)
                self._shadow_geom = g
            pad = _SHADOW_BLUR * 2
            QPainter(self).drawPixmap(g.left() - pad, g.top() - pad,
                                      self._shadow_pm)
        super().paintEvent(e)

    def _render_shadow(self, g) -> QPixmap:
        """Rectangle arrondi flouté une seule fois par géométrie (pyvips)."""
        import numpy as np

        from thermalright_lcd_control.device_controller.display import vips_utils as vu
        pad = _SHADOW_BLUR * 2
        w, h = g.width() + pad * 2, g.height() + pad * 2
        alpha = np.zeros((h, w), dtype=np.uint8)
        rw, rh, radius = g.width(), g.height(), 16   # radius : cf. QSS #lcdFrame
        yy, xx = np.mgrid[0:rh, 0:rw]
        cx = np.clip(xx, radius, rw - 1 - radius)
        cy = np.clip(yy, radius, rh - 1 - radius)
        inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2
        alpha[pad + _SHADOW_DY:pad + _SHADOW_DY + rh, pad:pad + rw] = inside * 140
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 3] = alpha
        img = vu.from_numpy(rgba).copy(interpretation="srgb").gaussblur(_SHADOW_BLUR / 2)
        return pixmap_from_vips(img)

    def set_empty(self, empty: bool) -> None:
        """Aucun device → écran gris vide, sans frame ni overlays."""
        self._empty = empty
        if empty:
            self.view.set_frame(QPixmap())
            self.view.setBackgroundBrush(Qt.darkGray)
        else:
            self.view.setBackgroundBrush(Qt.black)

    def _on_theme_loaded(self, payload: str) -> None:
        try:
            info = json.loads(payload)
        except Exception:
            return
        self._set_rotation(int(info.get("rotation") or 0))
        # Pré-remplit le champ « Save theme » avec le nom du thème chargé — sauf
        # quand c'est la config active du device (nom interne sans intérêt) : le
        # champ reste vide pour inviter à saisir un nom.
        self._theme_name.setText("" if info.get("is_active") else (info.get("name") or ""))

    # ── frames ────────────────────────────────────────────────────────────
    def _on_frame(self, jpeg_bytes) -> None:
        """Frame JPEG (bytes) du backend → QPixmap décodé nativement par Qt."""
        self._empty = False
        pm = QPixmap()
        pm.loadFromData(jpeg_bytes)
        self.view.set_frame(pm)

    # ── rotation ──────────────────────────────────────────────────────────
    def _on_rotate_pick(self, degrees: int) -> None:
        """L'utilisateur a choisi une rotation via les radios."""
        self._set_rotation(degrees)
        self.backend.set_rotation(self.rotation)

    def _set_rotation(self, degrees: int) -> None:
        self.rotation = degrees % 360
        self.view.set_rotation(self.rotation)
        btn = self._rot_buttons.get(self.rotation)
        if btn is not None and not btn.isChecked():
            # Sélection programmatique (thème chargé) : ne pas re-déclencher
            # idClicked / la sauvegarde backend.
            self._rot_group.blockSignals(True)
            btn.setChecked(True)
            self._rot_group.blockSignals(False)
        self.rotation_changed.emit(self.rotation)
