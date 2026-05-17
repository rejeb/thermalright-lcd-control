# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Backend applicatif de l'UI native (Qt Widgets).

``AppBackend`` est un :class:`QObject` qui possède toute la logique non
visuelle (thèmes, médias, config device, preview) et diffuse la frame LCD
rendue via le signal ``frame_ready_pil``. La fenêtre native s'y connecte par
signaux/slots ; il ne dépend d'aucun toolkit d'affichage particulier.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from thermalright_lcd_control.common.logging_config import get_gui_logger
from thermalright_lcd_control.device_controller.display.event_bus import Topic
from thermalright_lcd_control.gui.backend.mixins.backgrounds import BackgroundMixin
from thermalright_lcd_control.gui.backend.mixins.device_config import DeviceConfigMixin
from thermalright_lcd_control.gui.backend.mixins.foregrounds import ForegroundMixin
from thermalright_lcd_control.gui.backend.mixins.media_helpers import MediaHelpersMixin
from thermalright_lcd_control.gui.backend.mixins.overlay_style import OverlayStyleMixin
from thermalright_lcd_control.gui.backend.mixins.themes import ThemeMixin
from thermalright_lcd_control.gui.backend.mixins.thumbnails import ThumbnailMixin
from thermalright_lcd_control.gui.backend.mixins.window_chrome import WindowChromeMixin
from thermalright_lcd_control.gui.components import user_backgrounds
from thermalright_lcd_control.gui.components.thumbnail_cache import ThumbnailCache
from thermalright_lcd_control.gui.components.thumbnail_worker import ThumbnailWorker
from thermalright_lcd_control.gui.components.config_generator import ConfigGenerator
from thermalright_lcd_control.gui.components.preview_manager import PreviewManager

# 6 demo-mode hues — identical to the Qt grid (themes_tab._DEMO).
_DEMO_THEMES = [(206, "Config 1"), (28, "Config 2"), (150, "Config 3"),
                (280, "Config 4"), (45, "Config 5"), (340, "Config 6")]

def _text_anchor_gap(font_size: int, family: str | None = None,
                     bold: bool = False, italic: bool = False) -> tuple[int, int]:
    """The vips/Pango renderer draws the ink box top-left exactly at
    ``position``, so preview corner == render anchor: the PIL-era bearing
    offset is gone. Kept (returning (0, 0)) so save/load round-trips of the
    fx/fy math stay in one place."""
    return 0, 0


def _rgba_to_hex(color) -> str:
    """(r,g,b,a) → '#RRGGBBAA'. Accepts an RGB tuple or an already-hex string."""
    if isinstance(color, str):
        return color
    try:
        r, g, b = int(color[0]), int(color[1]), int(color[2])
        a = int(color[3]) if len(color) > 3 else 255
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
    except Exception:
        return "#FFFFFFFF"


# ── text style state: only ``font_family`` is read by PreviewManager ──────────
@dataclass
class TextStyle:
    font_family: str | None = None      # font path (None = system font)
    font_size: int = 18
    color: str = "#FFFFFF"                  # '#RRGGBB'


class OverlayWidgetsAdapter:
    """Adapte la liste de widgets overlay à l'interface attendue par ConfigGenerator.

    ``ConfigGenerator.generate_config_data_from_overlays`` calls
    :meth:`to_display_config` and expects a ``{metrics, date, time, texts}`` dict
    in the YAML format consumed by ``ConfigLoader``. Relative ``fx/fy`` positions
    are converted to pixels according to the device resolution.

    Note: ``DisplayConfig``/``ConfigLoader`` do not read the ``texts`` section —
    so *label* widgets are ignored (not saved) at this stage.
    """

    def __init__(self, widgets: list[dict], text_style: TextStyle,
                 dev_width: int, dev_height: int):
        self._widgets = widgets
        self._style = text_style
        self._w = dev_width
        self._h = dev_height

    def _font_size(self, w: dict) -> int:
        return int(w.get("font_size") or self._style.font_size)

    def _color(self, w: dict) -> str:
        c = w.get("color") or self._style.color or "#FFFFFF"
        if len(c) == 9:          # #RRGGBBAA
            return c
        if len(c) == 7:          # #RRGGBB → ajoute alpha opaque
            return c + "FF"
        return "#FFFFFFFF"

    def _pos(self, w: dict) -> dict:
        """fx/fy = coin haut-gauche *visible* → position d'ancrage PIL (− gap)."""
        st = self._style_of(w)
        gx, gy = _text_anchor_gap(self._font_size(w), st["font_family"],
                                  st["bold"], st["italic"])
        return {"x": max(0, int(round(w.get("fx", 0.5) * self._w - gx))),
                "y": max(0, int(round(w.get("fy", 0.5) * self._h - gy)))}

    @staticmethod
    def _style_of(w: dict) -> dict:
        """Font styling of a widget: family (None if empty) + bold/italic."""
        fam = w.get("font_family") or None
        return {"font_family": fam,
                "bold": bool(w.get("bold", False)),
                "italic": bool(w.get("italic", False))}

    def to_display_config(self) -> dict:
        metrics = [w for w in self._widgets if w.get("type") == "metric"]
        # Labels are now independent text overlays (``text``); ``metric_label``
        # is still accepted for any in-memory widget not yet migrated.
        text_widgets = [w for w in self._widgets
                        if w.get("type") in ("text", "metric_label")
                        and not w.get("hidden")
                        and (w.get("text") or "").strip()]
        clocks = [w for w in self._widgets if w.get("type") == "clock"]
        date_w = next((w for w in clocks if w.get("mode") == "date"), None)
        time_w = next((w for w in clocks if w.get("mode") == "time"), None)
        weekday_w = next((w for w in clocks if w.get("mode") == "weekday"), None)

        configs = []
        for w in metrics:
            st = self._style_of(w)
            configs.append({
                "name": w.get("key", ""),
                "precision": int(w.get("prec", 0)),
                "position": self._pos(w),
                "font_size": self._font_size(w),
                "color": self._color(w),
                "format_string": w.get("format_string") or "{value}{unit}",
                "unit": w.get("unit", ""),
                "enabled": True,
                "font_family": st["font_family"],
                "bold": st["bold"],
                "italic": st["italic"],
            })

        texts = []
        for w in text_widgets:
            st = self._style_of(w)
            texts.append({
                "text": w.get("text", ""),
                "position": self._pos(w),
                "font_size": self._font_size(w),
                "color": self._color(w),
                "enabled": True,
                "font_family": st["font_family"],
                "bold": st["bold"],
                "italic": st["italic"],
            })

        return {
            "metrics": {"enabled": bool(metrics), "configs": configs},
            "date": self._text_section(date_w),
            "time": self._text_section(time_w),
            "weekday": self._text_section(weekday_w),
            "texts": texts,
        }

    def _text_section(self, w: dict | None) -> dict:
        if w is None:
            return {"enabled": False, "text": "", "position": {"x": 0, "y": 0},
                    "font_size": self._style.font_size, "color": "#FFFFFFFF",
                    "font_family": None, "bold": False, "italic": False}
        st = self._style_of(w)
        return {"enabled": True, "text": "", "position": self._pos(w),
                "font_size": self._font_size(w), "color": self._color(w),
                "font_family": st["font_family"], "bold": st["bold"], "italic": st["italic"]}


class AppBackend(DeviceConfigMixin, WindowChromeMixin, BackgroundMixin,
                 ForegroundMixin, OverlayStyleMixin, ThemeMixin,
                 MediaHelpersMixin, ThumbnailMixin, QObject):
    """Backend applicatif complet exposé à la fenêtre native (signaux + méthodes)."""

    # Cadence min du preview : un preview n'a pas besoin du 30fps du device.
    # 66 ms ≈ 15 fps → moitié moins de frames à encoder/transporter/repeindre.
    _PREVIEW_MIN_INTERVAL_MS = 66

    # ── Signaux backend → UI ──────────────────────────────────────────────
    frame_ready_pil = Signal(object)  # frame JPEG (bytes) du LCD courant
    theme_loaded = Signal(str)      # JSON {name, rotation, fg_opacity}
    error_occurred = Signal(str)    # message d'erreur à afficher dans l'UI
    media_added = Signal(str)       # JSON {path, type} → rafraîchit la grille Backgrounds
    foreground_added = Signal()     # après import → rafraîchit la grille Foregrounds
    themes_refreshed = Signal()     # après un save → recharge la liste des thèmes
    widgets_loaded = Signal(str)    # JSON de _widgets → reconstruit les overlays
    window_state_changed = Signal(bool)  # True = maximisé
    device_changed = Signal()       # après switch device → recharge dims/thèmes/médias
    thumbnails_updated = Signal()    # worker cached new thumbnails → refresh grids
    devices_refreshed = Signal()    # après ajout d'un device → repeuple le combobox
    unsaved_changes_changed = Signal(bool)  # True = édits non sauvés (hint "Save config")

    def __init__(self, config: dict, devices: list[dict[str, Any]] | None,
                 event_bus=None, controller=None, config_path: str | None = None):
        super().__init__()
        self.logger = get_gui_logger()
        self.event_bus = event_bus
        self.controller = controller
        self.config = config
        # path to gui_config.yaml, used to persist UI preferences (e.g. theme)
        self.config_path = config_path

        # liste des devices configurés (cf. USBDeviceDetector) + device actif
        self.devices = devices or []
        self.device: dict[str, Any] = {}

        # backgrounds_base : racine des fonds ; le dossier réellement utilisé est
        # lié à la résolution (``<base>/<width><height>``) et résolu dans
        # :meth:`_apply_device`. ``media_endpoint`` sert au téléchargement à la
        # demande des fonds bundled (cf. :meth:`select_background`).
        paths = config.get("paths", {})
        self.backgrounds_base = paths.get(
            "backgrounds_dir", "./resources/themes/backgrounds")
        self.media_endpoint = config.get(
            "media_endpoint", "https://api.thermalright.com/")
        self.backgrounds_dir = self.backgrounds_base  # affiné par _apply_device

        # Thumbnail cache + background render worker. A cache miss on the GUI
        # thread returns a placeholder and enqueues the render here, so device
        # switching never blocks on image decoding.
        cache_dir = paths.get("thumbnail_cache") or os.path.join(
            os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
            "thermalright-lcd-control", "thumbnails")
        self._thumbnail_cache = ThumbnailCache(cache_dir)
        self._thumbnail_worker = ThumbnailWorker(
            self._thumbnail_cache, on_progress=self.thumbnails_updated.emit)
        self._thumbnail_worker.start()

        # état de rendu
        self.text_style = TextStyle()
        self.current_rotation = 0
        self.current_theme_name = ""
        # True quand la config affichée EST la config active du device (config_<id>)
        # → l'UI n'auto-remplit pas le champ « Save theme ».
        self._loaded_is_active = False
        # Édits non sauvegardés vs la config active sur disque : pilote le hint
        # visuel du bouton « Save config » (aucune auto-sauvegarde, cf. apply()).
        self._dirty = False
        self._window = None             # défini par main_window via set_window()
        # In-memory config per device (id → editable-state snapshot). A device's
        # config is read from disk only on its first load; every later switch back
        # restores from here so runtime edits survive device switches.
        self._device_states: dict[str, dict] = {}

        # overlays (metrics / clock / labels)
        self._widgets: list[dict] = []
        self._widget_uid = 1

        # PreviewManager ne rend plus : il ne porte que l'état d'édition (chemins,
        # rotation, opacité) lu par ConfigGenerator. Le preview lit le base frame
        # partagé du controller (cf. _tick).
        self.preview_manager = PreviewManager(config, None, self.text_style)

        # device actif → dimensions + dossiers liés à la résolution.
        # On amorce le ``config_<id>.yaml`` de CHAQUE device configuré (pas
        # seulement l'actif) : au premier lancement, un device auto-détecté non
        # actif n'a pas encore de config, son RenderEngine échoue à se construire
        # (fichier absent) et il n'obtient aucun generator — le preview resterait
        # alors bloqué sur le device actif. Le seeding des non-actifs passe par
        # ``_seed_device_config`` (léger : pas de switch, pas de téléchargement du
        # fond) ; l'actif est appliqué en dernier pour rester sélectionné.
        active = self.devices[0] if self.devices else {}
        for d in self.devices:
            if d is not active:
                self._seed_device_config(d)
        self._apply_device(active)

        # migration : adopter les anciens fonds user (stockés non redimensionnés)
        try:
            user_backgrounds.migrate_legacy(
                self._originals_dir(), Path(self.backgrounds_base), self._resolutions())
        except Exception as e:
            self.logger.warning(f"user backgrounds migration skipped: {e}")

        self.config_gen = ConfigGenerator(config)

        # métriques : collector partagé avec les moteurs de rendu (mêmes
        # capteurs, mêmes compteurs pour les débits)
        from thermalright_lcd_control.device_controller.metrics import shared_collector
        self._metrics = shared_collector()

        # boucle de frames (cap à _PREVIEW_MIN_INTERVAL_MS, ajustée pour
        # vidéo/GIF ; mise en pause quand la fenêtre n'est pas visible)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._PREVIEW_MIN_INTERVAL_MS)
        # Strong reference to the last base frame pushed to the preview: an
        # id() comparison would false-positive when a freed frame's address
        # is reused by the next allocation (frozen preview).
        self._last_base = None

        if self.event_bus is not None:
            self.event_bus.subscribe(Topic.DEVICES_CHANGED, self._on_devices_changed)

    # ── thumbnail warm ────────────────────────────────────────────────────
    def warm_thumbnails(self) -> None:
        """Pre-render every bundled background/foreground thumbnail for all
        device resolutions into the cache, in the background."""
        paths = self.config.get("paths", {})
        fg_base = paths.get("foregrounds_dir", "./resources/themes/foregrounds")
        video_exts = self._video_exts()
        resolutions = set()
        for d in self.devices:
            try:
                w, h = int(d.get("width", 320)), int(d.get("height", 240))
            except (TypeError, ValueError):
                continue
            resolutions.add(f"{w}{h}")
            resolutions.add(f"{h}{w}")          # rotated orientation
        for res in resolutions:
            self._warm_dir(Path(self.backgrounds_base) / res, video_exts, keep_alpha=False)
            self._warm_dir(Path(fg_base) / res, video_exts, keep_alpha=True)

    def _warm_dir(self, folder: Path, video_exts: set[str], keep_alpha: bool) -> None:
        if not folder.is_dir():
            return
        from thermalright_lcd_control.gui.components import thumbnail_render as tr
        for entry in folder.iterdir():
            if not entry.is_file():
                continue
            is_video = entry.suffix.lower() in video_exts
            self._thumbnail_worker.enqueue(
                str(entry), tr.THUMB_W, tr.THUMB_H, keep_alpha, is_video)

    # ── UI theme (light / dark) ───────────────────────────────────────────
    _UI_THEMES = ("light", "dark")

    def get_ui_theme(self) -> str:
        """UI color scheme chosen in-app: 'light' or 'dark'.

        Read from ``ui.theme`` in gui_config.yaml; defaults to 'dark'."""
        mode = self.config.get("ui", {}).get("theme", "dark")
        return mode if mode in self._UI_THEMES else "dark"

    def _confirm(self, title: str, message: str, *,
                 confirm_label: str = "Delete", destructive: bool = True) -> bool:
        """Frameless confirmation dialog matching the app chrome (replaces the
        distro-decorated QMessageBox). Returns True if the user confirms."""
        from thermalright_lcd_control.gui.native.confirm_dialog import ConfirmDialog
        dialog = ConfirmDialog(self._window, title, message,
                               confirm_label=confirm_label, destructive=destructive,
                               ui_theme=self.get_ui_theme(),
                               icon_path=self.config.get("paths", {}).get("icon_path", ""))
        return bool(dialog.exec())

    def set_ui_theme(self, mode: str) -> None:
        """Persist the UI theme choice into gui_config.yaml (``ui.theme``)."""
        if mode not in self._UI_THEMES:
            mode = "dark"
        self.config.setdefault("ui", {})["theme"] = mode
        if not self.config_path:
            return
        try:
            import yaml
            path = Path(self.config_path)
            data = {}
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            data.setdefault("ui", {})["theme"] = mode
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except Exception as e:
            self.logger.warning(f"set_ui_theme persist failed: {e}")

    # ══════════════════════════════════════════════════════════════════════
    #  Sauvegarde / Application
    # ══════════════════════════════════════════════════════════════════════
    def apply(self) -> None:
        """Génère + pousse vers le service (preview=True)."""
        self._persist(preview=True)

    def _set_dirty(self, value: bool) -> None:
        """Track unsaved edits and notify the UI only on change (drives the
        'Save config' hint). No auto-save is triggered."""
        if bool(value) != self._dirty:
            self._dirty = bool(value)
            self.unsaved_changes_changed.emit(self._dirty)

    def _persist(self, preview: bool) -> str:
        try:
            adapter = OverlayWidgetsAdapter(self._widgets, self.text_style,
                                            *self._media_res())
            self.preview_manager.current_rotation = self.current_rotation
            path = self.config_gen.generate_config_yaml_from_overlays(
                self.preview_manager, adapter, preview=preview,
                device_id=self.device.get("id"))
            if not preview:
                self.themes_refreshed.emit()
            elif self.event_bus is not None:
                from thermalright_lcd_control.device_controller.display.event_bus import Topic
                self.event_bus.publish(Topic.CONFIG_RELOAD, self.device.get("id"))
            # Saved → the active config on disk now matches memory: clear the hint.
            self._set_dirty(False)
            return json.dumps({"success": True, "path": path or ""})
        except Exception as e:
            self.logger.error(f"save/apply failed: {e}")
            self.error_occurred.emit(f"Save failed: {e}")
            return json.dumps({"success": False, "path": "", "error": str(e)})

    def _publish_live(self) -> None:
        """Push the current edit-state to the engine as an in-memory config.

        No file is written (that is what save()/apply() are for). The engine
        rebuilds its generator from this dict and the preview reflects it on the
        next base frame — no file round-trip (Part 2: live preview→device)."""
        # An edit diverged the in-memory config from the saved active config →
        # hint the user to save. Set before the event_bus guard so the hint works
        # even without a bus (preview-only sessions).
        self._set_dirty(True)
        if self.event_bus is None:
            return
        try:
            adapter = OverlayWidgetsAdapter(self._widgets, self.text_style,
                                            *self._media_res())
            self.preview_manager.current_rotation = self.current_rotation
            config_data = self.config_gen.generate_config_data_from_overlays(
                self.preview_manager, adapter)
            if config_data is None:
                return
            from thermalright_lcd_control.device_controller.display.event_bus import Topic
            self.event_bus.publish(Topic.CONFIG_RELOAD,
                                   self.device.get("id"), config_data)
        except Exception as e:
            self.logger.warning(f"live publish failed: {e}")


    # ══════════════════════════════════════════════════════════════════════
    #  Overlay widgets
    # ══════════════════════════════════════════════════════════════════════
    def add_widget(self, widget_json: str) -> str:
        """Ajoute un widget, lui assigne un id auto-incrémenté. Retourne {id}."""
        try:
            w = json.loads(widget_json)
        except Exception as e:
            self.logger.error(f"add_widget bad json: {e}")
            return json.dumps({"id": None})
        w["id"] = self._widget_uid
        self._widget_uid += 1
        self._widgets.append(w)
        self._publish_live()
        return json.dumps({"id": w["id"]})

    def update_widget(self, widget_json: str) -> None:
        """Met à jour le widget (id requis) dans ``self._widgets``."""
        try:
            patch = json.loads(widget_json)
        except Exception as e:
            self.logger.error(f"update_widget bad json: {e}")
            return
        wid = patch.get("id")
        for w in self._widgets:
            if w.get("id") == wid:
                w.update(patch)
                break
        self._publish_live()

    def delete_widget(self, widget_id: int) -> None:
        self._widgets = [w for w in self._widgets if w.get("id") != widget_id]
        self._publish_live()

    def get_widgets(self) -> str:
        return json.dumps(self._widgets)

    def _widgets_from_config(self, cfg) -> list[dict]:
        """Construit la liste de widgets éditables depuis un DisplayConfig.

        Les positions pixel (ancrage haut-gauche, comme le rendu) sont
        converties en positions relatives ``fx/fy`` pour l'éditeur d'overlays.
        """
        widgets: list[dict] = []

        # Normalize against the config's OUTPUT resolution (rotation-swapped by
        # ConfigLoader), not the raw device dims: a rotated theme stores its
        # positions in the ``<h><w>`` space, so using dev_width/dev_height would
        # misplace every widget after a rotation.
        norm_w = cfg.output_width or self.dev_width
        norm_h = cfg.output_height or self.dev_height

        def fx_fy(position, font_size, family=None,
                  bold=False, italic=False) -> tuple[float, float]:
            # position = ancrage PIL ; on remonte au coin visible (+ gap) puis on normalise
            gx, gy = _text_anchor_gap(font_size, family, bold, italic)
            x, y = position
            return ((x + gx) / norm_w if norm_w else 0.0,
                    (y + gy) / norm_h if norm_h else 0.0)

        # Metric = value only. Labels are independent ``text`` widgets built from
        # cfg.texts below (ConfigLoader migrates any legacy metric label there).
        for m in (cfg.metrics_configs or []):
            fx, fy = fx_fy(m.position, m.font_size, m.font_family, m.bold, m.italic)
            widgets.append({
                "id": self._widget_uid, "type": "metric", "key": m.name,
                "label": "", "unit": m.unit, "prec": m.precision,
                "format_string": m.format_string,
                "font_size": m.font_size, "color": _rgba_to_hex(m.color),
                "font_family": m.font_family, "bold": m.bold, "italic": m.italic,
                "fx": fx, "fy": fy,
            })
            self._widget_uid += 1

        # Standalone text overlays (labels, titles) — each with its OWN size/color.
        for t in (cfg.texts or []):
            fx, fy = fx_fy(t.position, t.font_size, t.font_family, t.bold, t.italic)
            widgets.append({
                "id": self._widget_uid, "type": "text", "text": t.text,
                "font_size": t.font_size, "color": _rgba_to_hex(t.color),
                "font_family": t.font_family, "bold": t.bold, "italic": t.italic,
                "hidden": False, "fx": fx, "fy": fy,
            })
            self._widget_uid += 1

        for clock_cfg, mode in ((cfg.date_config, "date"), (cfg.time_config, "time"),
                                (getattr(cfg, "weekday_config", None), "weekday")):
            if clock_cfg is not None:
                fx, fy = fx_fy(clock_cfg.position, clock_cfg.font_size,
                               clock_cfg.font_family, clock_cfg.bold, clock_cfg.italic)
                widgets.append({
                    "id": self._widget_uid, "type": "clock", "mode": mode,
                    "font_size": clock_cfg.font_size, "color": _rgba_to_hex(clock_cfg.color),
                    "font_family": clock_cfg.font_family, "bold": clock_cfg.bold,
                    "italic": clock_cfg.italic,
                    "fx": fx, "fy": fy,
                })
                self._widget_uid += 1

        return widgets

    # ══════════════════════════════════════════════════════════════════════
    #  Métriques
    # ══════════════════════════════════════════════════════════════════════
    def get_metrics(self) -> str:
        """JSON des métriques temps réel (None si capteur indisponible).

        Le collector partagé rafraîchit lui-même ses valeurs quand elles sont
        périmées ; l'appel est donc bon marché à la cadence du timer live."""
        return json.dumps(self._metrics.values())

    def get_fonts(self) -> str:
        """JSON list of available font family names for the inspector."""
        from thermalright_lcd_control.device_controller.display.font_manager import (
            list_font_families,
        )
        try:
            return json.dumps(list_font_families())
        except Exception as e:
            self.logger.warning(f"get_fonts failed: {e}")
            return json.dumps([])

    # ══════════════════════════════════════════════════════════════════════
    #  Boucle de frames
    # ══════════════════════════════════════════════════════════════════════
    def _tick(self) -> None:
        # Preview reads the controller's shared base frame for the active device
        # (Part 2: one generator feeds both preview and device).
        device_id = self.device.get("id") if self.device else None
        base = None
        if self.controller is not None and device_id is not None:
            base = self.controller.last_base_frame(device_id)
        if base is None:
            return
        if base is self._last_base:
            return                       # identical frame already shown (static bg)
        self._last_base = base
        try:
            # base is the generator's cached JPEG bytes: emitted as-is, the
            # preview hands them straight to QPixmap.loadFromData.
            self.frame_ready_pil.emit(base)
            # Cap the emit rate; the engine drives the true frame cadence.
            self._timer.setInterval(self._PREVIEW_MIN_INTERVAL_MS)
        except Exception as e:
            self.logger.warning(f"frame tick error: {e}")

    def set_preview_active(self, active: bool) -> None:
        """Fenêtre cachée (tray) ou minimisée → stoppe la boucle preview pour
        ne rien consommer côté GUI ; le RenderEngine continue d'alimenter le
        device. À la reprise, la frame courante est re-poussée immédiatement."""
        if active:
            if not self._timer.isActive():
                self._last_base = None
                self._timer.start(self._PREVIEW_MIN_INTERVAL_MS)
        else:
            self._timer.stop()
            self._last_base = None      # don't pin a frame of a dropped clip
        # Low-memory mode: minimized → engines drop the decoded media and keep
        # only the ready-to-send encoded cache.
        if self.controller is not None:
            setter = getattr(self.controller, "set_media_active", None)
            if callable(setter):
                setter(active)

    # ── lifecycle ─────────────────────────────────────────────────────────
    def cleanup(self) -> None:
        if self.event_bus is not None:
            self.event_bus.unsubscribe(Topic.DEVICES_CHANGED, self._on_devices_changed)
        self._timer.stop()
        if self.preview_manager:
            self.preview_manager.cleanup()
