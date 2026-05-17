# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""NativeMainWindow — UI 100 % Qt Widgets.

Assemble les modules natifs autour du :class:`AppBackend` : titlebar custom
(fenêtre frameless), panneau preview + éditeur d'overlays + contrôles
foreground à gauche, onglets médias/palette à droite. Le preview consomme
``frame_ready_pil`` (pixmap direct, sans encodage intermédiaire).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.common.logging_config import get_gui_logger
from thermalright_lcd_control.gui.backend.app_backend import AppBackend
from thermalright_lcd_control.gui.native.confirm_dialog import ConfirmDialog
from thermalright_lcd_control.gui.native.device_dialog import DeviceDialog
from thermalright_lcd_control.gui.native.foreground_controls import ForegroundControls
from thermalright_lcd_control.gui.native.overlay.editor import OverlayEditor
from thermalright_lcd_control.gui.native.overlay.inspector import WidgetInspector
from thermalright_lcd_control.gui.native.preview_panel import PreviewPanel
from thermalright_lcd_control.gui.native.tabs import SideTabs
from thermalright_lcd_control.gui.native.theme import build_qss, tokens
from thermalright_lcd_control.gui.native.titlebar import TitleBar
from thermalright_lcd_control.gui.native.toggle_switch import set_theme_colors as set_toggle_colors
from thermalright_lcd_control.gui.native.message_banner import MessageBanner
from thermalright_lcd_control.gui.native.update_banner import UpdateBanner, UpdateChecker
from thermalright_lcd_control.gui.shared.chrome import FramelessWindow
from thermalright_lcd_control.gui.shared.tray import TrayWindowMixin
from thermalright_lcd_control.gui.utils.config_loader import load_config


class NativeMainWindow(TrayWindowMixin, FramelessWindow):
    def __init__(self, config_file: str, devices: list[dict[str, Any] | None],
                 event_bus=None, controller=None):
        super().__init__()
        self.logger = get_gui_logger()
        self.setWindowTitle("ThermalRight LCD Control")

        # Fusion : seul style Qt qui respecte fidèlement nos sous-contrôles QSS
        # (flèches de QSpinBox, etc.) quel que soit le thème système sous-jacent.
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            # un clic hors du QLineEdit focus le libère (cf. blur() web)
            app.installEventFilter(self)

        self.config = load_config(config_file)

        self.backend = AppBackend(self.config, devices, event_bus=event_bus,
                                  controller=controller, config_path=config_file)
        self.backend.set_window(self)

        # ── composition ─────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = TitleBar(self.backend)
        root.addWidget(self.titlebar)

        # « new version available » banner, just under the titlebar (hidden until
        # the background check finds a newer release).
        self.update_banner = UpdateBanner()
        root.addWidget(self.update_banner)

        # bandeau message/erreur inline (même emplacement), p.ex. refus d'écraser
        # un thème préconfiguré.
        self.message_banner = MessageBanner()
        root.addWidget(self.message_banner)

        self.body = QGridLayout()
        self.body.setContentsMargins(14, 12, 14, 12)
        self.body.setSpacing(14)
        root.addLayout(self.body, 1)

        self.preview = PreviewPanel(self.backend)
        self.editor = OverlayEditor(self.backend, self.preview.view, parent=self)
        self.inspector = WidgetInspector(self.editor, self.backend)
        self.fg_controls = ForegroundControls(self.backend)

        # inspecteur + foreground : toujours co-localisés (cf. controls/wconf web)
        controls_lay = QVBoxLayout()
        controls_lay.setContentsMargins(0, 0, 0, 0)
        controls_lay.setSpacing(10)
        controls_lay.addWidget(self.inspector)
        controls_lay.addWidget(self.fg_controls)
        controls_lay.addStretch(1)
        self.controls_host = QWidget()
        self.controls_host.setLayout(controls_lay)

        # droite : onglets médias + palette
        self.tabs = SideTabs(self.backend)

        # séparateurs entre zones : vertical (contenu gauche | onglets),
        # horizontal (preview | contrôles, en défaut/wide) et horizontal
        # (contrôles | onglets, en tall, où ils sont tous deux à droite)
        self.vdivider = QFrame()
        self.vdivider.setObjectName("vDivider")
        self.vdivider.setFixedWidth(1)
        self.hdivider = QFrame()
        self.hdivider.setObjectName("vDivider")
        self.hdivider.setFixedHeight(1)
        self.hdivider2 = QFrame()
        self.hdivider2.setObjectName("vDivider")
        self.hdivider2.setFixedHeight(1)

        self._wide = False
        self._tall = False
        self._apply_body_layout(wide=False, tall=False)

        # barre d'état discrète pour les erreurs backend
        self._status = QLabel("")
        self._status.setObjectName("errText")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.hide()
        root.addWidget(self._status)

        # ── câblage backend ─────────────────────────────────────────────────
        self.backend.error_occurred.connect(self._show_error)
        self.backend.device_changed.connect(self.reload_for_device)
        # Coalesce worker progress bursts into a single visible-grid refresh.
        self._thumb_refresh_timer = QTimer(self)
        self._thumb_refresh_timer.setSingleShot(True)
        self._thumb_refresh_timer.setInterval(200)
        self._thumb_refresh_timer.timeout.connect(self._refresh_visible_thumbnails)
        self.backend.thumbnails_updated.connect(self._thumb_refresh_timer.start)
        # devices_refreshed → titlebar.reload_devices déjà connecté par TitleBar
        self.preview.view.widget_resizing.connect(self._sync_inspector_size)
        self.preview.device_size_changed.connect(lambda *_: self._update_responsive_layout())
        self.preview.rotation_changed.connect(lambda *_: self._update_responsive_layout())

        self.titlebar.add_device_requested.connect(self.open_add_device)
        self.titlebar.edit_device_requested.connect(self.open_edit_device)
        self.titlebar.delete_device_requested.connect(self.delete_selected_device)
        self.titlebar.ui_theme_changed.connect(self.apply_ui_theme)
        self.preview.save_theme_requested.connect(self._save_theme)
        self.preview.save_config_requested.connect(self._apply_config)

        # thème + dimensions
        self.apply_ui_theme(self.backend.get_ui_theme())
        wc = self.config.get("window", {})
        min_w = wc.get("min_width", 900)
        min_h = wc.get("min_height", 640)
        self.setMinimumSize(min_w, min_h)
        self.resize(max(wc.get("default_width", 1180), min_w),
                    max(wc.get("default_height", 800), min_h))

        self._init_tray_lifecycle(controller)

        # premier chargement (dims, thèmes, médias du device actif)
        self._last_media_res = None
        self.reload_for_device()
        self._update_responsive_layout()
        # aucun device configuré → ouvrir directement le formulaire d'ajout
        if not devices:
            QTimer.singleShot(0, self.open_add_device)
        # Warm the thumbnail cache in the background so first paint isn't delayed.
        QTimer.singleShot(0, self.start_thumbnail_warm)
        # Best-effort startup check for a newer release (opt-out via config).
        if self.config.get("updates", {}).get("check_on_startup", True):
            self._update_checker = UpdateChecker(parent=self)
            self._update_checker.update_available.connect(
                self.update_banner.show_update)
            QTimer.singleShot(0, self._update_checker.start)

    def _set_ui_active(self, active: bool) -> None:
        """Tray/minimisée : coupe aussi le rafraîchissement live de l'éditeur."""
        super()._set_ui_active(active)
        self.editor.set_live_updates(active)

    # ── thème UI ──────────────────────────────────────────────────────────
    def apply_ui_theme(self, mode: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(mode))
        self.titlebar.set_icon_color(QColor(tokens(mode)["dim"]))
        t = tokens(mode)
        set_toggle_colors(t["accent"], t["toggle_off"])

    def eventFilter(self, obj, e):
        # relâche le focus d'un QLineEdit dès qu'on clique ailleurs (blur web)
        if e.type() == QEvent.MouseButtonPress:
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit) and obj is not fw:
                target = obj if isinstance(obj, QWidget) else None
                if target is None or not fw.isAncestorOf(target):
                    fw.clearFocus()
        return super().eventFilter(obj, e)

    # ── disposition responsive (port de l'ancienne UI web) ──────────────────
    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._update_responsive_layout()

    def _update_responsive_layout(self) -> None:
        # device_w/device_h already come pre-oriented for the current rotation
        # (PreviewPanel.reload_device_info() reads them from get_device_info(),
        # which swaps for 90°/270° via _media_res()) — do not swap again here.
        eff_w, eff_h = self.preview.device_w, self.preview.device_h
        win_w, win_h = max(self.width(), 1), max(self.height(), 1)

        # le grand côté du preview vaut au moins 75 % de la résolution réelle,
        # avec un plancher basé sur 25 % de la largeur fenêtre
        min_long = 0.75 * max(eff_w, eff_h)
        box = max(160, round(win_w * 0.25), round(min_long))
        eff_ar = (eff_w / eff_h) if eff_h else 1.0
        if eff_ar >= 1:
            sw, sh = box, round(box / eff_ar)
        else:
            sh, sw = box, round(box * eff_ar)
        # plafond : un device plus grand que la fenêtre doit être réduit pour
        # tenir à l'écran (sinon setFixedSize déborde et le preview est tronqué)
        scale = min(1.0, 0.92 * win_w / max(sw, 1), 0.80 * win_h / max(sh, 1))
        if scale < 1.0:
            sw, sh = round(sw * scale), round(sh * scale)
        self.preview.set_target_box(sw, sh)

        wide = sw > 0.40 * win_w
        tall = sh > 0.70 * win_h

        # zone contrôles (inspecteur + foreground) : au moins 25 % de la largeur
        # fenêtre quand le preview est étalé en pleine largeur (disposition wide)
        self.controls_host.setMinimumWidth(round(0.25 * win_w) if wide else 0)

        if wide != self._wide or tall != self._tall:
            self._wide, self._tall = wide, tall
            self._apply_body_layout(wide, tall)

    def _apply_body_layout(self, wide: bool, tall: bool) -> None:
        """Réorganise la grille (preview / contrôles / onglets) — port de
        Même logique que l'ancienne UI web : ``wide`` étale le preview en pleine largeur
        (contrôles à côté des onglets) ; ``tall`` (sans ``wide``) remonte les
        contrôles au-dessus des onglets, à droite. 3 lignes dans les deux cas où
        le preview surplombe les contrôles (défaut / wide), pour la ligne de
        séparation horizontale entre les deux."""
        body = self.body
        all_widgets = (self.preview, self.controls_host, self.tabs,
                       self.vdivider, self.hdivider, self.hdivider2)
        for w in all_widgets:
            body.removeWidget(w)
            # removeWidget() only detaches from the layout, it does NOT hide the
            # widget — left visible, a divider unused in the new mode would stay
            # painted at its last position (e.g. the wide-mode hdivider lingering
            # after switching to tall). Hide everything, then show only what
            # this mode actually places below.
            w.hide()

        # colonne 0 = contenu gauche, colonne 1 = séparateur (1px), colonne 2 = onglets
        # 4 lignes disponibles : seul « tall » utilise la 4e (contrôles/onglets empilés)
        if wide:
            used = (self.preview, self.hdivider, self.controls_host, self.vdivider, self.tabs)
            body.addWidget(self.preview, 0, 0, 1, 3, Qt.AlignHCenter | Qt.AlignTop)
            body.addWidget(self.hdivider, 1, 0, 1, 3)
            body.addWidget(self.controls_host, 2, 0)
            body.addWidget(self.vdivider, 2, 1)
            body.addWidget(self.tabs, 2, 2)
        elif tall:
            used = (self.preview, self.vdivider, self.controls_host, self.hdivider2, self.tabs)
            body.addWidget(self.preview, 0, 0, 4, 1, Qt.AlignHCenter | Qt.AlignTop)
            body.addWidget(self.vdivider, 0, 1, 4, 1)
            body.addWidget(self.controls_host, 0, 2)
            body.addWidget(self.hdivider2, 1, 2)
            body.addWidget(self.tabs, 2, 2, 2, 1)
        else:
            used = (self.preview, self.hdivider, self.controls_host, self.vdivider, self.tabs)
            body.addWidget(self.preview, 0, 0, Qt.AlignHCenter | Qt.AlignTop)
            body.addWidget(self.hdivider, 1, 0)
            body.addWidget(self.controls_host, 2, 0)
            body.addWidget(self.vdivider, 0, 1, 3, 1)
            body.addWidget(self.tabs, 0, 2, 3, 1)

        for w in used:
            w.show()

        body.setColumnStretch(0, 0)
        body.setColumnStretch(1, 0)
        body.setColumnStretch(2, 1)
        body.setRowStretch(0, 0)
        body.setRowStretch(1, 1)
        body.setRowStretch(2, 1)
        body.setRowStretch(3, 1 if tall else 0)

    # ── rechargement lié au device actif ──────────────────────────────────
    def reload_for_device(self) -> None:
        self.preview.reload_device_info()
        # Key on the MEDIA resolution (rotation-swapped), not the raw device
        # dimensions: a rotation changes the media folder (<w><h> ↔ <h><w>) while
        # dev_width/dev_height stay put, so keying on the latter would wrongly
        # skip reloading the backgrounds/foregrounds for the new orientation.
        res = self.backend._media_res()
        same_res = (res == getattr(self, "_last_media_res", None))
        self._last_media_res = res
        # Themes always reload: the "Current theme" tile is device-specific.
        # A reload triggered by a ROTATION only happens when the orientation
        # actually flipped (landscape ↔ portrait): a 0°↔180° / 90°↔270° turn
        # keeps the same media resolution so _sync_rotation_dirs short-circuits
        # and never reaches here. The current theme was built for the previous
        # orientation, so it no longer corresponds to the new one → drop to the
        # first preset (persisted as the new "Current theme" by set_rotation's
        # apply() right after this reload). On a genuine DEVICE SWITCH select the
        # device's own "Current theme" (index 0), which _ensure_active_config
        # guarantees exists (saved config, else first preset copied in).
        rotating = getattr(self.backend, "_rotation_reload", False)
        themes = self.tabs.load_themes()
        if not same_res:
            # Backgrounds/foregrounds are resolution-scoped and identical across
            # same-resolution devices — only reload when the (media) resolution
            # changed (device switch OR rotation).
            self.tabs.load_backgrounds()
            self.tabs.load_foregrounds()
        active = self.backend._active_config_file()
        if rotating and themes:
            # The pre-rotation active config no longer matches the new orientation
            # → load the first preset for the new orientation into the live preview
            # (not persisted — the user saves explicitly if they want to keep it).
            self.preview.set_empty(False)
            active_res = active.resolve() if active else None
            presets = [t for t in themes if t.get("yaml_path")
                       and Path(t["yaml_path"]).resolve() != active_res]
            target = presets[0] if presets else themes[0]
            self.backend.select_theme(target.get("yaml_path", ""))
        elif self.backend.has_device_state():
            # Switching back to a device already loaded this session → restore its
            # in-memory config (no disk read; preserves unsaved runtime edits).
            self.preview.set_empty(False)
            self.backend.restore_device_state()
        elif active is not None:
            # First load of this device this session: read its active config from
            # disk into the preview (no grid tile — the grid only lists presets).
            self.preview.set_empty(False)
            self.backend.select_theme(str(active))
        elif themes:
            self.preview.set_empty(False)
            self.backend.select_theme(themes[0].get("yaml_path", ""))
        else:
            # aucun device/thème → preview gris vide
            self.preview.set_empty(True)
            self.editor.load_widgets("[]")

    def _refresh_visible_thumbnails(self) -> None:
        """Reload the grids for the current tab (now cache hits) so placeholders
        are replaced with real thumbnails."""
        self.tabs.load_all()

    def start_thumbnail_warm(self) -> None:
        self.backend.warm_thumbnails()

    # ── save / apply ──────────────────────────────────────────────────────
    def _save_theme(self, name: str) -> None:
        try:
            res = json.loads(self.backend.save_theme(name))
        except Exception as e:
            self.message_banner.show_message(f"Save failed: {e}")
            return
        if res.get("success"):
            self.message_banner.hide()      # clear any previous error
            self.preview.clear_theme_name()
        elif not res.get("cancelled"):      # cancelled overwrite → stay silent
            # Inline banner under the header (e.g. refusing to overwrite a
            # preconfigured theme), instead of a modal dialog.
            self.message_banner.show_message(res.get("error") or "Save failed")
        self.tabs.load_themes()

    def _apply_config(self) -> None:
        self.backend.apply()
        # apply met à jour la config active (tuile « Current theme »)
        self.tabs.load_themes()

    # ── devices ───────────────────────────────────────────────────────────
    def open_add_device(self) -> None:
        dialog = DeviceDialog(self.backend, parent=self)
        if dialog.exec():
            self.titlebar.reload_devices()

    def open_edit_device(self) -> None:
        device_id = self.titlebar.current_device_id()
        if not device_id:       # entrée legacy sans id → non éditable
            self._show_error("No editable device selected (legacy entry without id)")
            return
        try:
            cfg = json.loads(self.backend.get_device_config(device_id))
        except Exception:
            cfg = {}
        if not cfg.get("id"):       # entrée legacy sans id → non éditable
            self._show_error("No editable device selected (legacy entry without id)")
            return
        dialog = DeviceDialog(self.backend, parent=self, edit_config=cfg)
        if dialog.exec():
            self.titlebar.reload_devices()

    def delete_selected_device(self) -> None:
        device_id = self.titlebar.current_device_id()
        if not device_id:       # entrée legacy sans id → non supprimable
            self._show_error("No deletable device selected (legacy entry without id)")
            return
        dialog = ConfirmDialog(
            self, "Confirm deletion",
            f'Delete device "{device_id}"?\nThis removes its device file and '
            f'deletes its saved configuration.',
            confirm_label="Delete", ui_theme=self.backend.get_ui_theme(),
            icon_path=self.backend.config.get("paths", {}).get("icon_path", ""))
        if not dialog.exec():
            return
        try:
            res = json.loads(self.backend.delete_device(device_id))
        except Exception as e:
            self._show_error(str(e))
            return
        if res.get("success"):
            self.titlebar.reload_devices()
        else:
            self._show_error(res.get("error") or "Delete failed")

    # ── divers ────────────────────────────────────────────────────────────
    def _sync_inspector_size(self, wid: int) -> None:
        w = self.editor.find(wid)
        if w is not None:
            self.inspector.sync_size_value(w)

    def _show_error(self, message: str) -> None:
        self.logger.error(f"UI error: {message}")
        self._status.setText(message)
        self._status.show()
        QTimer.singleShot(6000, self._status.hide)
