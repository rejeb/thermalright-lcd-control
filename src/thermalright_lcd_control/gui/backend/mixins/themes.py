# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Theme slots: list/select/reset/delete and active-config seeding.

Mixed into :class:`AppBackend`; reads ``self.themes_dir``, ``self.device``,
``self.dev_width``/``self.dev_height``, ``self.preview_manager``,
``self.backgrounds_dir``, ``self.config`` and the ``theme_loaded``/
``themes_refreshed``/``widgets_loaded``/``error_occurred`` signals, and uses the
media/thumbnail/background helpers from the host.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml

# User-saved themes are named ``config_YYYYMMDD_HHMMSS.yaml`` (cf. ConfigGenerator).
_USER_THEME_RE = re.compile(r"^config_\d{8}_\d{6}$")


class ThemeMixin:
    # ── active-config seeding ─────────────────────────────────────────────
    def _ensure_active_config(self, *, download_background: bool = True) -> None:
        """Create the device's active config (``config_<id>.yaml``) when missing.

        Order: keep an existing id-keyed config; else seed from a legacy
        resolution-keyed config (back-compat); else copy the first preset theme;
        else build a minimal config from the first background. If nothing is
        available, leave it absent (the preview stays empty).

        ``download_background=False`` skips the on-demand fetch of the bundled
        background: seeding a non-active device only needs the config *file* to
        exist so its engine can build — the engine fetches the media lazily on
        start, so downloading it here would just be redundant startup I/O."""
        from thermalright_lcd_control.device_controller.display.device_config import (
            legacy_config_path,
            resolve_active_config,
        )
        device_id = self.device.get("id")
        cfg_dir = self._config_dir()
        if device_id:
            target = resolve_active_config(cfg_dir, str(device_id),
                                           self.dev_width, self.dev_height)
        else:
            target = legacy_config_path(cfg_dir, self.dev_width, self.dev_height)
        if target.exists():
            if download_background:
                self._ensure_config_background(target)
            return
        if self._seed_active_from_preset(target):
            if download_background:
                self._ensure_config_background(target)
            return
        self._seed_active_from_background(target)

    def _ensure_config_background(self, cfg_path: Path) -> None:
        """Télécharge à la demande le fond bundled référencé par la config
        active s'il manque sur le disque (config seedée d'un preset, ou copiée
        avant que le ``.mp4`` n'ait été téléchargé).

        FrameManager télécharge désormais paresseusement au moment du rendu,
        mais l'endpoint configuré (``self.media_endpoint``) n'est connu que
        côté GUI : le moteur reconstruit sa config sans cet endpoint. On
        préchauffe donc ici avec le bon endpoint. ConfigLoader résout
        ``{resolution}`` (avec permutation rotation) avant le téléchargement —
        un parsing YAML manuel ici resterait bloqué sur un ``{resolution}``
        littéral pour les configs sauvées après ce fix."""
        try:
            from thermalright_lcd_control.device_controller.display.asset_download import (
                ensure_background_downloaded,
            )
            from thermalright_lcd_control.device_controller.display.config import (
                BackgroundType,
            )
            from thermalright_lcd_control.device_controller.display.config_loader import (
                ConfigLoader,
            )
            cfg = ConfigLoader().load_config(str(cfg_path), self.dev_width, self.dev_height,
                                             media_endpoint=self.media_endpoint)
            if cfg.background_type == BackgroundType.VIDEO:
                ensure_background_downloaded(cfg.background_path, self.media_endpoint)
        except Exception as e:
            self.logger.warning(f"ensure config background failed: {e}")

    def _seed_active_from_preset(self, target: Path) -> bool:
        """Copy the first preset theme for the resolution into ``target``."""
        presets = self._yaml_files()
        if not presets:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(presets[0], target)
        self.logger.info(f"Seeded active config from preset {presets[0].name}")
        return True

    def _seed_active_from_background(self, target: Path) -> bool:
        """Write a minimal config whose only content is the first background."""
        bg = self._first_background_file()
        if bg is None:
            return False
        config_data = {"display": {
            "rotation": 0,
            "background": {"path": str(bg),
                           "type": self.preview_manager.determine_background_type(str(bg)).value},
            "foreground": {"enabled": False, "path": "",
                           "position": {"x": 0, "y": 0}, "alpha": 1.0},
            "metrics": {"enabled": False, "configs": []},
            "date": {"enabled": False},
            "time": {"enabled": False},
            "texts": [],
        }}
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        self.logger.info(f"Seeded active config from background {bg.name}")
        return True

    def _first_background_file(self) -> Path | None:
        """First supported media in the device's backgrounds dir (or None)."""
        bg_dir = Path(self.backgrounds_dir)
        if not bg_dir.exists():
            return None
        fmts = self.config.get("supported_formats", {})
        exts = (set(fmts.get("images", [])) | set(fmts.get("videos", []))
                | set(fmts.get("gifs", [])))
        for p in sorted(bg_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in exts:
                return p
        return None

    def _active_config_file(self) -> Path | None:
        """Path of the active config the device is currently rendering
        (``config_<id>.yaml``, else resolution-keyed). ``None`` if it does not
        exist yet (fresh install)."""
        from thermalright_lcd_control.device_controller.display.device_config import (
            active_config_path,
            legacy_config_path,
        )
        cfg_dir = self._config_dir()
        device_id = self.device.get("id")
        path = (active_config_path(cfg_dir, device_id) if device_id
                else legacy_config_path(cfg_dir, self.dev_width, self.dev_height))
        return path if path.exists() else None

    # ── theme listing / selection ─────────────────────────────────────────
    def get_themes(self) -> str:
        """JSON: theme list [{name, yaml_path, thumbnail}].

        Lists ONLY the preset themes for the active device resolution: ``themes_dir``
        is ``presets/<width><height>``. If none match the list is empty (the UI shows
        "No themes found.") — no demo themes, and no "Current" tile: the device's
        active config is loaded into the preview on startup but not shown as a tile.
        """
        # No device configured → no themes at all (no "Current theme", the
        # preview stays empty). Themes only make sense for a device resolution.
        if not self.device:
            return json.dumps([])

        themes: list[dict[str, str]] = []
        try:
            for yaml_path in self._yaml_files():
                cfg = self._resolve_theme_cfg(yaml_path)
                bg = self._bg_image_from_cfg(cfg)
                themes.append({
                    "name": self._display_name(yaml_path),
                    "yaml_path": str(yaml_path.absolute()),
                    "removable": self._is_user_theme(yaml_path),
                    # Composite preview (background + foreground + widgets), not
                    # just the background.
                    "thumbnail": self._theme_thumbnail(yaml_path, cfg, bg),
                })
        except Exception as e:
            self.logger.error(f"Error listing themes: {e}")

        return json.dumps(themes)

    def select_theme(self, yaml_path: str, persist: bool = False) -> None:
        """Load the theme via ConfigLoader and apply it to the PreviewManager.

        ``persist=True`` also writes the loaded theme to the device's active
        config (``config_<id>.yaml``) so it survives a restart. The themes grid no
        longer passes this: clicking a theme is a live preview only, and the user
        persists explicitly via Apply/Save. Both the grid click and the
        programmatic reloads (device switch, rotation, startup) pass ``False``:
        they only mirror the config into the preview without writing to disk."""
        try:
            if yaml_path.startswith("demo:"):
                self.current_theme_name = yaml_path[len("demo:"):]
                self._loaded_is_active = False
                self.preview_manager.initialize_default_background(self.backgrounds_dir)
                self._widgets = []
                self._publish_live()
                self._emit_theme_loaded()
                self.widgets_loaded.emit(self.get_widgets())
                if persist:
                    self.apply()
                return

            from thermalright_lcd_control.device_controller.display.config_loader import (
                ConfigLoader,
            )
            # A theme file's ``rotation`` is authoritative ONLY when loading the
            # device's own active config ("Current theme") OUTSIDE a rotation —
            # that restores the saved orientation on startup. In every other case
            # keep the current rotation:
            #  * preset themes always store rotation 0 and must not snap the user
            #    back to 0° (they'd then load the wrong-orientation media);
            #  * during a rotation reload the rotation was just set by the user,
            #    so the active config must load for that NEW orientation, not the
            #    stale saved one.
            # ``rotation_override`` resolves the config's ``{resolution}`` assets
            # to the current orientation folder, so rotating reloads the theme
            # (background/foreground/widgets) for the new resolution.
            rotating = getattr(self, "_rotation_reload", False)
            active = self._active_config_file()
            is_active = (active is not None
                         and Path(yaml_path).resolve() == active.resolve())
            rot_override = None if (is_active and not rotating) else self.current_rotation
            cfg = ConfigLoader().load_config(yaml_path, self.dev_width, self.dev_height,
                                             rotation_override=rot_override,
                                             media_endpoint=self.media_endpoint)
            self.current_theme_name = self._display_name(Path(yaml_path))

            self.current_rotation = cfg.rotation
            self.preview_manager.set_rotation(self.current_rotation)
            self._sync_rotation_dirs()

            # background (downloads the bundled .mp4 on demand if needed)
            if cfg.background_path:
                self.preview_manager.set_background(
                    self._resolve_bundled_background(cfg.background_path))

            # foreground
            if cfg.foreground_image_path:
                self.preview_manager.set_foreground(cfg.foreground_image_path)
                self.preview_manager.set_foreground_opacity(cfg.foreground_alpha)
            else:
                self.preview_manager.clear_foreground()

            # overlays configured in the theme → editable widgets
            self._widgets = self._widgets_from_config(cfg)
            self._publish_live()
            # Loading the device's OWN active config (startup / device switch) leaves
            # nothing unsaved; picking a DIFFERENT theme diverges from the saved
            # config → keep the "Save config" hint lit (_publish_live set it).
            self._loaded_is_active = bool(is_active and not rotating)
            if is_active and not rotating:
                self._set_dirty(False)
            self._emit_theme_loaded()
            self.widgets_loaded.emit(self.get_widgets())
            # User pick → save it as the device's current theme right away.
            if persist:
                self.apply()
        except Exception as e:
            self.logger.error(f"Error loading theme {yaml_path}: {e}")
            self.error_occurred.emit(f"Could not load theme: {e}")

    def reset_preview(self) -> None:
        """Reset the preview: default background, no foreground or overlays.

        Called on a device/resolution change when the new resolution has no theme:
        otherwise the previous theme would stay displayed."""
        try:
            self.current_theme_name = ""
            self._loaded_is_active = False
            self.current_rotation = 0
            self.preview_manager.current_rotation = 0
            self._sync_rotation_dirs()
            self.preview_manager.clear_all(self.backgrounds_dir)
            self._widgets = []
            self._publish_live()
            self._emit_theme_loaded()
            self.widgets_loaded.emit(self.get_widgets())
        except Exception as e:
            self.logger.error(f"reset_preview failed: {e}")

    def delete_theme(self, yaml_path: str) -> None:
        """Delete a user custom theme: only the YAML file in ``themes_dir``. Does
        not remove any background/foreground. Refuses bundled presets."""
        try:
            p = Path(yaml_path).resolve()
            if p.parent != self.themes_dir.resolve():
                raise ValueError("target outside the themes folder")
            if not self._is_user_theme(p):
                raise ValueError("default theme is not removable")
            if not self._confirm("Confirm deletion",
                                 f'Delete theme "{self._display_name(p)}"?'):
                return
            if p.exists():
                p.unlink()
            self.themes_refreshed.emit()        # the UI reloads the themes grid
        except Exception as e:
            self.logger.error(f"delete_theme failed: {e}")
            self.error_occurred.emit(f"Delete failed: {e}")

    # ── saving a named theme ──────────────────────────────────────────────
    def save_theme(self, name: str) -> str:
        """Save the current config as a named theme (``user_<slug>.yaml``).

        JSON result ``{success, error?}``. Refuses to overwrite a bundled default
        theme; overwriting an existing user theme asks for confirmation first."""
        try:
            name = (name or "").strip()
            if not name:
                return json.dumps({"success": False,
                                   "error": "Please enter a theme name."})
            slug = self._slugify(name)
            if not slug:
                return json.dumps({"success": False,
                                   "error": "Invalid theme name."})

            existing = self._find_theme_by_name(name)
            if existing is not None:
                if not self._is_user_theme(existing):
                    return json.dumps({"success": False,
                        "error": f'"{name}" is a built-in theme and cannot be '
                                 f'overwritten. Choose another name.'})
                # overwriting a user theme → confirm
                if not self._confirm(
                        "Overwrite theme?",
                        f'A theme named "{name}" already exists. Overwrite it?',
                        confirm_label="Overwrite"):
                    return json.dumps({"success": False, "cancelled": True})
                target = existing
            else:
                target = self.themes_dir / f"user_{slug}.yaml"

            from thermalright_lcd_control.gui.backend.app_backend import (
                OverlayWidgetsAdapter,
            )
            adapter = OverlayWidgetsAdapter(self._widgets, self.text_style,
                                            *self._media_res())
            self.preview_manager.current_rotation = self.current_rotation
            path = self.config_gen.generate_config_yaml_from_overlays(
                self.preview_manager, adapter, preview=False,
                device_id=self.device.get("id"), theme_path=target)
            self.current_theme_name = self._display_name(target)
            self._set_dirty(False)          # saved → clear the "Save config" hint
            self.themes_refreshed.emit()
            return json.dumps({"success": True, "path": path or str(target)})
        except Exception as e:
            self.logger.error(f"save_theme failed: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # ── helpers ───────────────────────────────────────────────────────────
    def _emit_theme_loaded(self) -> None:
        fg_path = self.preview_manager.current_foreground_path
        self.theme_loaded.emit(json.dumps({
            "name": self.current_theme_name,
            "is_active": getattr(self, "_loaded_is_active", False),
            "rotation": self.current_rotation,
            "fg_opacity": self.preview_manager.foreground_opacity,
            "fg_enabled": bool(fg_path),
            "fg_path": fg_path or "",
        }))

    def _yaml_files(self) -> list[Path]:
        if not self.themes_dir.exists():
            return []
        files: list[Path] = []
        for pat in ("*.yaml", "*.yml"):
            files.extend(self.themes_dir.glob(pat))
        files.sort()
        return files

    @staticmethod
    def _display_name(f: Path) -> str:
        stem = f.stem
        if stem.startswith("user_"):        # named theme → drop the storage prefix
            stem = stem[len("user_"):]
        name = stem.replace("_", " ").replace("-", " ")
        return " ".join(w.capitalize() for w in name.split())

    @staticmethod
    def _is_user_theme(f: Path) -> bool:
        """True if the theme was saved by the user: a named theme (``user_<name>``)
        or a legacy timestamped one (``config_<ts>``). Bundled presets
        (``theme_<n>``) are not user themes and must not be overwritten."""
        return f.stem.startswith("user_") or bool(_USER_THEME_RE.match(f.stem))

    @staticmethod
    def _slugify(name: str) -> str:
        """Filesystem-safe slug for a user-typed theme name."""
        slug = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower()).strip("_")
        return slug

    def _find_theme_by_name(self, name: str) -> Path | None:
        """Existing theme whose display name matches ``name`` (case-insensitive)."""
        target = name.strip().casefold()
        for f in self._yaml_files():
            if self._display_name(f).casefold() == target:
                return f
        return None

    def _resolve_theme_cfg(self, yaml_path: Path):
        """Load a theme's DisplayConfig for listing/thumbnail (best-effort, None
        on error). Resolving a config never triggers a download (FrameManager owns
        that, lazily at read time). Resolve at the CURRENT rotation so a rotated
        theme's ``{resolution}`` assets point at the right orientation folder."""
        try:
            from thermalright_lcd_control.device_controller.display.config_loader import (
                ConfigLoader,
            )
            return ConfigLoader().load_config(
                str(yaml_path), self.dev_width, self.dev_height,
                rotation_override=self.current_rotation)
        except Exception as e:
            self.logger.warning(f"Cannot resolve config for {yaml_path}: {e}")
            return None

    def _bg_image_from_cfg(self, cfg) -> str:
        """Resolve a loaded config's background to a local IMAGE path (best-effort,
        empty string if none). Never downloads: a bundled video falls back to its
        same-named PNG thumbnail."""
        if cfg is None:
            return ""
        try:
            from thermalright_lcd_control.device_controller.display.config import BackgroundType
            path = cfg.background_path
            if not path:
                return ""
            if cfg.background_type == BackgroundType.IMAGE_COLLECTION:
                p = Path(path)
                if p.is_dir():
                    for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"):
                        hits = sorted(p.glob(ext))
                        if hits:
                            return str(hits[0])
                return ""
            # Bundled background (.mp4): the video may not be downloaded yet, but
            # its same-named PNG thumbnail always is — use it.
            p = Path(path)
            if (cfg.background_type == BackgroundType.VIDEO
                    and not p.name.startswith("user_")
                    and self._same_path(p.parent, self.backgrounds_dir)):
                png = p.with_suffix(".png")
                if png.exists():
                    return str(png)
            return path if p.exists() else ""
        except Exception as e:
            self.logger.warning(f"Cannot resolve background: {e}")
            return ""

    def _background_of(self, yaml_path: Path) -> str:
        """Resolve the theme's background image (kept for callers wanting only
        the background)."""
        return self._bg_image_from_cfg(self._resolve_theme_cfg(yaml_path))
