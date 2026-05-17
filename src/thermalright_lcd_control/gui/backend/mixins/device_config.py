# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Device-config slots: active-device management and devices.yaml CRUD.

Mixed into :class:`AppBackend`; reads ``self.device``/``self.devices``,
``self.controller``, ``self.config``, ``self.preview_manager``,
``self.backgrounds_base`` and the ``device_changed``/``devices_refreshed``/
``error_occurred`` signals, and uses the theme/background helpers from the host.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from thermalright_lcd_control.gui.components import user_backgrounds


class DeviceConfigMixin:
    # ── active device management ──────────────────────────────────────────
    @staticmethod
    def _coerce_int(value) -> int | None:
        """vid/pid may be an int or a hex/dec string ('0x0416') depending on how
        the entry was written to devices.yaml. Normalise to int."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        try:
            return int(str(value), 0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _device_key(device: dict[str, Any]) -> str:
        """Stable identifier of a device for the combobox.

        In generic mode the ``id`` is mandatory and unique: it is used as the key
        so two devices sharing the same ``vid:pid`` (e.g. two simulated
        resolutions) stay distinct. Falls back to ``"<vid>:<pid>"`` in legacy mode
        (entry without id)."""
        device_id = device.get("id")
        if device_id:
            return str(device_id)
        vid = DeviceConfigMixin._coerce_int(device.get("vid"))
        pid = DeviceConfigMixin._coerce_int(device.get("pid"))
        return f"{vid}:{pid}"

    @staticmethod
    def _device_label(device: dict[str, Any]) -> str:
        """Readable label: ``"0x0416:0x5302 · <id>"``.

        Shows the device ``id`` (generic mode) so the user can identify the
        selected config; falls back to the resolution when the entry has no id
        (legacy mode)."""
        vid = DeviceConfigMixin._coerce_int(device.get("vid"))
        pid = DeviceConfigMixin._coerce_int(device.get("pid"))
        ids = (f"{hex(vid)}:{hex(pid)}"
               if vid is not None and pid is not None else "—")
        device_id = device.get("id")
        suffix = device_id if device_id else \
            f"{device.get('width', '?')}×{device.get('height', '?')}"
        return f"{ids} · {suffix}"

    def _apply_device(self, device: dict[str, Any]) -> None:
        """Activate ``device``: update dimensions and the resolution-bound folders
        (``themes_dir`` / ``foregrounds_dir`` / ``backgrounds_dir``) and propagate
        the dimensions to the PreviewManager. Each media folder is suffixed with
        ``<width><height>`` so it only serves the device-resolution backgrounds.
        Called at init and on each switch via :meth:`select_device`."""
        self.device = device or {}
        self.dev_width = int(self.device.get("width", 320))
        self.dev_height = int(self.device.get("height", 240))

        self._refresh_media_dirs()
        self.preview_manager.set_device_dimensions(*self._media_res())

        # Ensure the device has an active config so a "Current theme" exists and
        # the engine has something to render (seeded from the first preset, else
        # the first background). No-op when no device is active. Skip the disk
        # read (background prewarm) when the device is already held in memory:
        # its config was read — and media fetched — on first load, so switching
        # back uses the in-memory config, never the disk file.
        if self.device:
            already = self.device.get("id") in getattr(self, "_device_states", {})
            try:
                self._ensure_active_config(download_background=not already)
            except Exception as e:
                self.logger.warning(f"ensure active config failed: {e}")

    def _seed_device_config(self, device: dict[str, Any]) -> None:
        """Seed ``device``'s active config (``config_<id>.yaml``) so its engine
        can build, WITHOUT switching to it.

        Unlike :meth:`_apply_device` this is a bootstrap-only helper: it sets the
        device-scoped state the seeding reads (dimensions + media folders) and
        creates the config file if missing, but does not touch the preview
        dimensions and does not download the background (the engine fetches it
        lazily). A malformed device dict is skipped, not raised, so one bad
        entry can't crash startup. The caller re-applies the active device last,
        which resets ``self.device``/dimensions/folders."""
        self.device = device or {}
        if not self.device:
            return
        try:
            self.dev_width = int(self.device.get("width", 320))
            self.dev_height = int(self.device.get("height", 240))
        except (TypeError, ValueError) as e:
            self.logger.warning(f"skip seeding device with invalid size: {e}")
            return
        self._refresh_media_dirs()
        try:
            self._ensure_active_config(download_background=False)
        except Exception as e:
            self.logger.warning(f"seed device config failed: {e}")

    def _media_res(self) -> tuple[int, int]:
        """Résolution côté médias : dimensions device, permutées en 90°/270°
        (même règle que ConfigLoader, pour rester cohérent avec la résolution
        des chemins background/foreground)."""
        from thermalright_lcd_control.device_controller.display.config_loader import (
            resolve_resolution_for_rotation,
        )
        return resolve_resolution_for_rotation(
            self.dev_width, self.dev_height, self.current_rotation)

    def _refresh_media_dirs(self) -> None:
        """Thèmes/backgrounds/foregrounds : deux variantes par device —
        ``<w><h>`` en 0°/180°, ``<h><w>`` en 90°/270° (médias déjà orientés)."""
        w, h = self._media_res()
        paths = self.config.get("paths", {})
        self.themes_dir = Path(
            f"{paths.get('themes_dir', './resources/themes/presets')}/{w}{h}")
        self.foregrounds_dir = Path(
            f"{paths.get('foregrounds_dir', './resources/themes/foregrounds')}/{w}{h}")
        self.backgrounds_dir = str(Path(self.backgrounds_base) / f"{w}{h}")

    def _sync_rotation_dirs(self) -> None:
        """Changement de rotation = changement d'orientation : re-résout les
        dossiers et, s'ils ont changé, recharge l'UI comme un changement de
        device (grilles thèmes/backgrounds/foregrounds + dimensions preview)."""
        old = (self.backgrounds_dir, str(self.foregrounds_dir), str(self.themes_dir))
        self._refresh_media_dirs()
        self.preview_manager.set_device_dimensions(*self._media_res())
        if old == (self.backgrounds_dir, str(self.foregrounds_dir), str(self.themes_dir)):
            return
        # garde anti-réentrance : reload_for_device sélectionne un thème, dont le
        # load repasse ici ; on n'émet pas device_changed depuis ce rechargement.
        if getattr(self, "_rotation_reload", False):
            return
        self._rotation_reload = True
        try:
            self.device_changed.emit()
        finally:
            self._rotation_reload = False

    def _reapply_active(self, key: str) -> None:
        """Re-resolve the active device in the reloaded list (by key) and
        re-apply it, to refresh dimensions/folders and bind ``self.device`` to the
        up-to-date object. No-op if the key is no longer present."""
        match = next((d for d in self.devices if self._device_key(d) == key), None)
        if match is not None:
            self._apply_device(match)

    def _on_devices_changed(self, devices: list[dict[str, Any]]) -> None:
        """EventBus Topic.DEVICES_CHANGED handler: mirrors the presence-
        filtered device list published by DevicePresenceMonitor. May run on
        the controller thread; only touches ``self.devices``/``self.device``
        (plain assignment) and Qt signals — both safe from a non-GUI thread
        (PySide auto-queues signal delivery to slots living on the main
        thread)."""
        self.devices = list(devices)
        if self.device:
            active_key = self._device_key(self.device)
            if any(self._device_key(d) == active_key for d in self.devices):
                self._reapply_active(active_key)   # rebind to the fresh object
            else:
                self._apply_device(self.devices[0] if self.devices else {})
                if self.controller is not None:
                    self.controller.active_device_id = (
                        self.device.get("id") if self.device else None)
                self.device_changed.emit()
        self.devices_refreshed.emit()

    def get_device_info(self) -> str:
        """JSON: {vid, pid, width, height, label}."""
        vid = self._coerce_int(self.device.get("vid"))
        pid = self._coerce_int(self.device.get("pid"))
        label = (f"{hex(vid)}:{hex(pid)}"
                 if vid is not None and pid is not None else "—")
        w, h = self._media_res()      # dimensions orientées (90°/270° → h×w)
        return json.dumps({
            "vid": vid, "pid": pid,
            "width": w, "height": h,
            "label": label,
            # Current (in-memory) rotation so PreviewPanel.reload_device_info()
            # restores the live orientation instead of snapping the radios to 0°
            # (which would revert an unsaved rotation on the next reload).
            "rotation": self.current_rotation,
        })

    def get_devices(self) -> str:
        """JSON: list of configured devices for the header combobox.

        ``[{key, label, vid, pid, width, height, current}]`` — ``current`` marks
        the active device. The list comes from ``USBDeviceDetector`` (devices.yaml,
        else device_info.yaml), passed in at init."""
        active = self._device_key(self.device)
        return json.dumps([{
            "key": self._device_key(d),
            "label": self._device_label(d),
            "id": d.get("id"),
            "vid": d.get("vid"), "pid": d.get("pid"),
            "width": d.get("width"), "height": d.get("height"),
            "current": self._device_key(d) == active,
            "auto": bool(d.get("auto_detected")),
        } for d in self.devices])

    def select_device(self, key: str) -> None:
        """Activate the device whose ``"<vid>:<pid>"`` key matches ``key``.

        Reconfigures dimensions and (resolution) folders, then emits
        ``device_changed``: the UI reloads device info / themes / media."""
        try:
            match = next((d for d in self.devices
                          if self._device_key(d) == key), None)
            if match is None:
                raise ValueError(f"unknown device: {key}")
            if self._device_key(match) == self._device_key(self.device):
                return                      # already active → no-op
            # No auto-save of the outgoing device's config: the user decides when
            # to save (Save button). But keep the outgoing device's in-memory edit
            # state so switching back restores it WITHOUT re-reading disk — during a
            # running session the config lives in memory (disk is read only on the
            # device's first load). reload_for_device restores it via
            # restore_device_state() when a snapshot exists.
            if self.device.get("id"):
                self._device_states[self.device["id"]] = self._capture_device_state()
            # Pre-apply the incoming device's saved rotation (if it has an in-memory
            # snapshot) so _apply_device resolves the media dirs for the right
            # orientation up front — restore_device_state then finds them already
            # correct and won't fire a reentrant rotation-reload from disk.
            incoming = self._device_states.get(match.get("id"))
            if incoming is not None:
                self.current_rotation = incoming["rotation"]
            self._apply_device(match)
            if self.controller is not None:
                self.controller.set_active_device(match.get("id"))
            self.device_changed.emit()
        except Exception as e:
            self.logger.error(f"select_device failed: {e}")
            self.error_occurred.emit(f"Device switch failed: {e}")

    # ── per-device in-memory config (no disk read on switch) ──────────────
    def has_device_state(self) -> bool:
        """True if the active device's config is already held in memory (loaded
        earlier this session). When True, reload_for_device restores it from
        memory instead of re-reading the disk config."""
        dev_id = self.device.get("id")
        return bool(dev_id) and dev_id in self._device_states

    def _capture_device_state(self) -> dict:
        """Snapshot the current device's editable in-memory state (background,
        foreground, overlay widgets, rotation, theme name). No file is written —
        this is the in-memory config kept across device switches."""
        pm = self.preview_manager
        return {
            "theme_name": self.current_theme_name,
            "rotation": self.current_rotation,
            "background": pm.current_background_path,
            "foreground": pm.current_foreground_path,
            "foreground_opacity": pm.foreground_opacity,
            "widgets": copy.deepcopy(self._widgets),
            "dirty": self._dirty,
            "is_active": self._loaded_is_active,
        }

    def restore_device_state(self) -> bool:
        """Restore the active device's in-memory snapshot into the preview/engine
        (same effect as loading its theme, but from memory — no disk read).
        Returns False if there is no snapshot for the active device."""
        state = self._device_states.get(self.device.get("id"))
        if state is None:
            return False
        self.current_theme_name = state["theme_name"]
        self.current_rotation = state["rotation"]
        self.preview_manager.set_rotation(self.current_rotation)
        # re-resolve the media dirs / preview dimensions for this device+rotation
        # (self-heals the grids via the reentrant reload, exactly as select_theme).
        self._sync_rotation_dirs()
        if state["background"]:
            self.preview_manager.set_background(state["background"])
        if state["foreground"]:
            self.preview_manager.set_foreground(state["foreground"])
            self.preview_manager.set_foreground_opacity(state["foreground_opacity"])
        else:
            self.preview_manager.clear_foreground()
        self._widgets = copy.deepcopy(state["widgets"])
        self._loaded_is_active = state.get("is_active", False)
        self._publish_live()            # sets dirty=True; restore the saved flag
        self._set_dirty(state.get("dirty", False))
        self._emit_theme_loaded()
        self.widgets_loaded.emit(self.get_widgets())
        return True

    # ── adding a new device (generic model) ───────────────────────────────
    def _config_dir(self) -> str:
        return self.config.get("paths", {}).get("service_config", "./resources/config")

    def _load_devices_yaml(self) -> list[dict[str, Any]]:
        """Every device from the per-device ``device_<id>.yaml`` files."""
        from thermalright_lcd_control.device_controller.display import device_registry
        try:
            return device_registry.list_devices(self._config_dir())
        except (OSError, yaml.YAMLError) as e:
            self.logger.error(f"Cannot read device files: {e}")
            return []

    def get_usb_devices(self) -> str:
        """JSON: all USB devices (lsusb view) → [{vid, pid, name, label}]."""
        from thermalright_lcd_control.device_controller.display import device_registry
        try:
            return json.dumps(device_registry.list_usb_devices())
        except Exception as e:
            self.logger.error(f"get_usb_devices failed: {e}")
            return "[]"

    def detect_devices(self) -> str:
        """JSON: probe-registry scan of connected hardware.

        Each item is a ``device_registry.detect_devices`` result: the device's
        self-reported screen (handshake PM/FBL) merged with the wire-family
        defaults into a ready-to-use config. Reserved for future UI; the
        add/edit flows don't call it.
        """
        from thermalright_lcd_control.device_controller.display import device_registry
        try:
            return json.dumps(device_registry.detect_devices())
        except Exception as e:
            self.logger.error(f"detect_devices failed: {e}")
            return "[]"

    def suggest_device_id(self, vid: str, pid: str, bus: str, device: str) -> str:
        """Suggest a unique id ``pid_vid_bus_device`` (physical USB address)."""
        from thermalright_lcd_control.device_controller.display import device_registry
        try:
            return device_registry.suggest_id(
                self._load_devices_yaml(), vid, pid, bus, device)
        except Exception as e:
            self.logger.error(f"suggest_device_id failed: {e}")
            return ""

    def _resolution_supported(self, width, height) -> bool:
        """A resolution is supported when a ``<width><height>`` background folder
        exists under ``backgrounds_base`` (e.g. ``320240``)."""
        try:
            w, h = int(width), int(height)
        except (TypeError, ValueError):
            return False
        if w <= 0 or h <= 0:
            return False
        return (Path(self.backgrounds_base) / f"{w}{h}").is_dir()

    def get_supported_resolutions(self) -> str:
        """JSON: ``[[width, height], …]`` triés — résolutions device déduites des
        dossiers ``<width><height>`` de ``backgrounds_base``.

        Les noms sont des concaténations ambiguës présentes dans les deux ordres
        (wxh et hxw) ; spec device : ``width >= height`` et ``width <= 1920`` —
        seules les découpes qui respectent ces règles (sans zéro de tête) et
        dont le dossier miroir ``<height><width>`` existe aussi (lève les
        découpes ambiguës, ex. ``172640`` → 1726×40) sont des résolutions
        device. Noms non numériques (suffixes de variantes, ``{resolution}``)
        ignorés."""
        try:
            names = {e.name for e in Path(self.backgrounds_base).iterdir()
                     if e.is_dir() and e.name.isdigit()}
        except OSError as e:
            self.logger.error(f"Cannot list background folders: {e}")
            names = set()
        found: set[tuple[int, int]] = set()
        for name in names:
            for i in range(1, len(name)):
                ws, hs = name[:i], name[i:]
                if ws.startswith("0") or hs.startswith("0"):
                    continue
                w, h = int(ws), int(hs)
                if h <= w <= 1920 and f"{h}{w}" in names:
                    found.add((w, h))
        return json.dumps(sorted(found))

    def check_resolution(self, width: str, height: str) -> str:
        """JSON {supported: bool}: whether a background folder exists for the
        ``<width><height>`` resolution the user typed in the device form."""
        return json.dumps({"supported": self._resolution_supported(width, height)})

    def check_native_driver(self, vid: str, pid: str, width: str, height: str) -> str:
        """JSON {available: bool} : une classe driver native (legacy) existe pour
        ce (vid, pid, width, height) — sinon le formulaire device masque le
        choix du mode driver (Generic est le seul possible)."""
        from thermalright_lcd_control.common.supported_devices import find_legacy_class
        v, p = self._coerce_int(vid), self._coerce_int(pid)
        try:
            w, h = int(width), int(height)
        except (TypeError, ValueError):
            w = h = 0
        available = (v is not None and p is not None
                     and find_legacy_class(v, p, w, h) is not None)
        return json.dumps({"available": available})

    def add_device(self, payload: str) -> str:
        """Validate the form and add the entry to devices.yaml.

        Returns JSON {success, id?, error?}. Emits ``devices_refreshed`` on success.
        """
        from thermalright_lcd_control.device_controller.display import device_registry
        try:
            form = json.loads(payload)
            if not self._resolution_supported(form.get("width"), form.get("height")):
                return json.dumps({"success": False, "error": (
                    f"Unsupported resolution {form.get('width')}×{form.get('height')}: "
                    f"no matching background folder exists.")})
            entry = device_registry.build_device_entry(form)
            device_registry.write_device_entry(self._config_dir(), entry)
            self.devices = self._load_devices_yaml()
            # materialize the existing user backgrounds at the new device resolution
            w, h = int(entry["width"]), int(entry["height"])
            user_backgrounds.materialize_for(
                self._originals_dir(), Path(self.backgrounds_base), w, h)
            # Activate the device just added so the GUI switches to it
            # (dims/themes/media) BEFORE devices_refreshed : le combobox du
            # header se resélectionne via le flag ``current`` de get_devices().
            match = next((d for d in self.devices
                          if str(d.get("id")) == str(entry["id"])),
                         self.devices[0] if self.devices else None)
            if match is not None:
                self._apply_device(match)
                if self.controller is not None:
                    # affectation directe : add_device_engine() juste après
                    # construit déjà l'engine avec le bon active_device_id
                    # (set_active_device serait redondant ici)
                    self.controller.active_device_id = match.get("id")
            self.devices_refreshed.emit()
            if match is not None:
                self.device_changed.emit()
            if self.controller is not None:
                self.controller.add_device_engine(entry["id"])
            return json.dumps({"success": True, "id": entry["id"]})
        except Exception as e:
            # last-resort: surface error to the UI without crashing the backend
            # (body spans JSON parsing, YAML I/O and USB enumeration).
            self.logger.error(f"add_device failed: {e}")
            return json.dumps({"success": False, "error": str(e)})

    def get_device_config(self, device_id: str) -> str:
        """JSON: the devices.yaml entry of device ``device_id`` (for editing)."""
        from thermalright_lcd_control.device_controller.display import device_registry
        try:
            cfg = device_registry.get_device(self._config_dir(), device_id)
            return json.dumps(cfg or {})
        except Exception as e:
            self.logger.error(f"get_device_config failed: {e}")
            return "{}"

    def update_device(self, original_id: str, payload: str) -> str:
        """Update the ``original_id`` entry in devices.yaml.

        If the id changes, also rename the active config ``config_<id>.yaml``.
        Always resets preview/themes/media (``device_changed``). Returns JSON
        {success, id?, error?}; also emits ``devices_refreshed``."""
        from thermalright_lcd_control.device_controller.display import device_registry
        from thermalright_lcd_control.device_controller.display.device_config import (
            active_config_path,
        )
        try:
            form = json.loads(payload)
            if not self._resolution_supported(form.get("width"), form.get("height")):
                return json.dumps({"success": False, "error": (
                    f"Unsupported resolution {form.get('width')}×{form.get('height')}: "
                    f"no matching background folder exists.")})
            # Editing must not launder an auto-detected entry into a deletable
            # one: carry the flag over from the original entry (the dialog form
            # never contains it).
            original = next((d for d in self.devices
                             if self._device_key(d) == original_id), None)
            if original is not None and original.get("auto_detected"):
                form["auto_detected"] = True
            entry = device_registry.build_device_entry(form)
            edited_active = self._device_key(self.device) == original_id
            device_registry.update_device_entry(
                self._config_dir(), original_id, entry)
            # rename the active config if the id changed
            if entry["id"] != original_id:
                cfg_dir = self._config_dir()
                old = active_config_path(cfg_dir, original_id)
                new = active_config_path(cfg_dir, entry["id"])
                if old.exists() and not new.exists():
                    old.rename(new)
            self.devices = self._load_devices_yaml()
            # materialize the user backgrounds at the (new) resolution of the edited device
            w, h = int(entry["width"]), int(entry["height"])
            user_backgrounds.materialize_for(
                self._originals_dir(), Path(self.backgrounds_base), w, h)
            # re-apply the active device (dimensions/folders) then reset the UI
            target_key = entry["id"] if edited_active else self._device_key(self.device)
            self._reapply_active(target_key)
            # keep the controller's previewed id in sync with a renamed active
            # device; direct assignment — update_device_engine() below rebuilds
            # just this device's engine (set_active_device would be redundant)
            if edited_active and self.controller is not None:
                self.controller.active_device_id = entry["id"]
            self.devices_refreshed.emit()
            self.device_changed.emit()
            if self.controller is not None:
                self.controller.update_device_engine(original_id, entry["id"])
            return json.dumps({"success": True, "id": entry["id"]})
        except Exception as e:
            self.logger.error(f"update_device failed: {e}")
            return json.dumps({"success": False, "error": str(e)})

    def delete_device(self, device_id: str) -> str:
        """Delete the ``device_id`` entry from devices.yaml and its active config.

        If the deleted device was active, switch to the first remaining one.
        Always resets preview/themes/media (``device_changed``). Returns JSON
        {success, error?}; also emits ``devices_refreshed``."""
        from thermalright_lcd_control.device_controller.display import device_registry
        from thermalright_lcd_control.device_controller.display.device_config import (
            active_config_path,
        )
        try:
            target = next((d for d in self.devices
                           if self._device_key(d) == device_id), None)
            if target is not None and target.get("auto_detected"):
                # Startup-probe entries are managed by the service: deleting one
                # would only get it re-added on the next launch.
                return json.dumps({"success": False,
                                   "error": "Auto-detected devices cannot be removed"})
            deleted_active = self._device_key(self.device) == device_id
            device_registry.remove_device_entry(self._config_dir(), device_id)
            cfg_dir = self._config_dir()
            cfg = active_config_path(cfg_dir, device_id)
            if cfg.exists():
                cfg.unlink()
            self.devices = self._load_devices_yaml()
            # active device deleted → switch to the first remaining one (else keep active)
            if deleted_active:
                self._apply_device(self.devices[0] if self.devices else {})
                # sync the controller's previewed id, otherwise the deleted
                # device's replacement engine stays media-inactive (no base
                # frames) and the preview keeps showing the deleted device's
                # last frame; direct assignment — remove_device_engine() below
                # only tears down the deleted device's own engine
                if self.controller is not None:
                    self.controller.active_device_id = (
                        self.device.get("id") if self.device else None)
            else:
                self._reapply_active(self._device_key(self.device))
            self.devices_refreshed.emit()
            self.device_changed.emit()
            if self.controller is not None:
                self.controller.remove_device_engine(device_id)
            return json.dumps({"success": True})
        except Exception as e:
            self.logger.error(f"delete_device failed: {e}")
            return json.dumps({"success": False, "error": str(e)})
