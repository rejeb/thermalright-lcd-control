# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from pathlib import Path
from typing import Dict, Any, Tuple

import yaml

from .config import DisplayConfig, BackgroundType, MetricConfig, TextConfig
from ...common.logging_config import LoggerConfig


class ConfigLoader:
    """Load and parse YAML configuration files with global font support"""

    def __init__(self):
        self.logger = self.logger = LoggerConfig.setup_service_logger()

    def _hex_to_rgba(self, hex_color: str) -> Tuple[int, int, int, int]:
        """Convert hex color (#RRGGBBAA) to RGBA tuple"""
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]

        if len(hex_color) == 8:  # RRGGBBAA
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16)
            return (r, g, b, a)
        elif len(hex_color) == 6:  # RRGGBB (assume full alpha)
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b, 255)
        else:
            raise ValueError(f"Invalid hex color format: {hex_color}")

    def _parse_metric_config(self, metric_data: Dict[str, Any]) -> MetricConfig:
        """Parse a metric configuration from YAML data (no font_path needed)"""
        return MetricConfig(
            name=metric_data["name"],
            label=metric_data.get("label", ""),
            position=(
                metric_data["position"]["x"],
                metric_data["position"]["y"]
            ),
            font_size=metric_data["font_size"],
            color=self._hex_to_rgba(metric_data["color"]),
            format_string=metric_data.get("format_string", "{label}{value}"),
            unit=metric_data.get("unit", ""),
            enabled=metric_data.get("enabled", True)
        )

    def _parse_text_config(self, text_data: Dict[str, Any]) -> TextConfig:
        """Parse a text configuration from YAML data (no font_path needed)"""
        return TextConfig(
            text=text_data.get("text", ""),
            position=(
                text_data["position"]["x"],
                text_data["position"]["y"]
            ),
            font_size=text_data["font_size"],
            color=self._hex_to_rgba(text_data["color"]),
            enabled=text_data.get("enabled", True)
        )

    def load_config(self, config_path: str) -> DisplayConfig:
        """Load configuration from YAML file"""
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, 'r', encoding='utf-8') as file:
                yaml_data = yaml.safe_load(file)

            config = self.load_config_from_dict(yaml_data)
            self.logger.info(f"Configuration loaded successfully from {config_path}")
            return config
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def load_config_from_dict(self, yaml_data: dict) -> DisplayConfig:
        display_data = yaml_data["display"]
        # Parse metrics configurations
        metrics_configs = []
        if display_data["metrics"]["enabled"]:
            for metric_data in display_data["metrics"]["configs"]:
                if metric_data.get("enabled", True):
                    metrics_configs.append(self._parse_metric_config(metric_data))
        # Parse date configuration
        date_config = None
        if display_data["date"]["enabled"]:
            date_config = self._parse_text_config(display_data["date"])
        # Parse time configuration
        time_config = None
        if display_data["time"]["enabled"]:
            time_config = self._parse_text_config(display_data["time"])
        # Parse foreground configuration
        foreground_path = None
        foreground_position = (0, 0)
        foreground_alpha = 1.0
        if display_data["foreground"]["enabled"]:
            foreground_path = display_data["foreground"]["path"]
            foreground_position = (
                display_data["foreground"]["position"]["x"],
                display_data["foreground"]["position"]["y"]
            )
            foreground_alpha = display_data["foreground"]["alpha"]
        config = DisplayConfig(
            background_path=display_data["background"]["path"],
            background_type=BackgroundType(display_data["background"]["type"]),
            foreground_image_path=foreground_path,
            foreground_position=foreground_position,
            foreground_alpha=foreground_alpha,
            metrics_configs=metrics_configs,
            date_config=date_config,
            time_config=time_config
        )

        return config
