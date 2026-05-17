# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Configuration YAML generator (overlay-aware)."""

from datetime import datetime
from pathlib import Path

import yaml

from thermalright_lcd_control.common.logging_config import get_gui_logger


class ConfigGenerator:
    """Generates YAML configuration files from the current UI state."""

    def __init__(self, config):
        self.config = config
        self.logger = get_gui_logger()

    # ====================================================================
    #  NEW: build the theme from the dynamic overlay list (OverlayManager)
    # ====================================================================
    def generate_config_data_from_overlays(self, preview_manager, overlay_manager) -> dict | None:
        try:
            foreground_path = self._add_resolution_placeholder(
                preview_manager.current_foreground_path,
                preview_manager.preview_width, preview_manager.preview_height)
            background_path = self._add_resolution_placeholder(
                preview_manager.current_background_path,
                preview_manager.preview_width, preview_manager.preview_height)

            overlays = overlay_manager.to_display_config()

            return {
                "display": {
                    "rotation": preview_manager.current_rotation,
                    "background": {
                        "path": background_path or "",
                        "type": preview_manager.determine_background_type(
                            preview_manager.current_background_path).value,
                    },
                    "foreground": {
                        "enabled": preview_manager.current_foreground_path is not None,
                        "path": foreground_path,
                        "position": {"x": 0, "y": 0},
                        "alpha": preview_manager.foreground_opacity,
                    },
                    "metrics": overlays["metrics"],
                    "date": overlays["date"],
                    "time": overlays["time"],
                    "weekday": overlays.get("weekday", {"enabled": False}),
                    "texts": overlays["texts"],
                }
            }
        except Exception as e:
            self.logger.error(f"Error generating config from overlays: {e}")
            return None

    def generate_config_yaml_from_overlays(self, preview_manager, overlay_manager,
                                           preview: bool = False,
                                           device_id: str | None = None,
                                           theme_path: "Path | None" = None) -> str | None:
        try:
            config_data = self.generate_config_data_from_overlays(preview_manager, overlay_manager)
            if config_data is None:
                return None

            service_path = self._get_service_config_file_path(
                preview_manager.preview_width, preview_manager.preview_height,
                device_id=device_id)
            self._save_config_file(service_path, config_data)

            if not preview:
                # Named theme (from the "Save theme" field) → its explicit path;
                # else a timestamped file (legacy behaviour).
                config_path = theme_path or self._get_new_config_file_path(
                    preview_manager.preview_width, preview_manager.preview_height)
                config_path.parent.mkdir(parents=True, exist_ok=True)
                self._save_config_file(config_path, config_data)
                return f"{config_path.absolute()}"
        except Exception as e:
            self.logger.error(f"Error generating config YAML: {e}")
        return None

    # ====================================================================
    #  helpers
    # ====================================================================
    def _get_new_config_file_path(self, dev_width, dev_height) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        themes_dir = f"{self.config.get('paths', {}).get('themes_dir', './themes')}/{dev_width}{dev_height}"
        Path(themes_dir).mkdir(parents=True, exist_ok=True)
        return Path(themes_dir) / f"config_{timestamp}.yaml"

    def _get_service_config_file_path(self, dev_width, dev_height,
                                      device_id: str | None = None) -> Path | None:
        try:
            service_config_dir = self.config.get('paths', {}).get('service_config', './config')
            Path(service_config_dir).mkdir(parents=True, exist_ok=True)
            if device_id:
                # Generic mode: active config keyed by device id (config_<id>.yaml).
                from thermalright_lcd_control.device_controller.display.device_config import (
                    active_config_path,
                )
                return active_config_path(service_config_dir, device_id)
            # Legacy mode: resolution-keyed active config (unchanged).
            return Path(f"{service_config_dir}/config_{dev_width}{dev_height}.yaml")
        except Exception as e:
            self.logger.error(f"Error building service config path: {e}")
            return None

    def _save_config_file(self, config_path: Path, config_data: dict) -> str | None:
        if config_path is None or config_data is None:
            return None
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        return str(config_path)

    def _add_resolution_placeholder(self, path: str, width: int, height: int) -> str | None:
        return path.replace(f"/{width}{height}/", "/{resolution}/") if path is not None else None
