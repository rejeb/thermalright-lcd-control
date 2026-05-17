# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from pathlib import Path
from typing import Any

import yaml

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.device_controller.display.asset_download import (
    DEFAULT_MEDIA_ENDPOINT,
)
from thermalright_lcd_control.device_controller.display.config import (
    BackgroundType,
    DisplayConfig,
    MetricConfig,
    TextConfig,
)


def resolve_resolution_for_rotation(width: int, height: int, rotation: int) -> tuple[int, int]:
    """Canvas/asset-folder dimensions to use for a given device size and
    rotation. 0°/180° keep ``width x height``; 90°/270° swap to
    ``height x width`` since the composed canvas (background/foreground/
    widgets, never pixel-rotated) is built in the swapped orientation and
    only the final frame sent to the device is transposed back.

    Module-level so callers outside :class:`ConfigLoader` (e.g. the GUI's
    device-config mixin, for media-folder browsing) share the exact same
    swap rule instead of reimplementing it."""
    if rotation in (90, 270):
        return height, width
    return width, height


class ConfigLoader:
    """Load and parse YAML configuration files with global font support"""

    def __init__(self):
        self.logger = LoggerConfig.setup_service_logger()

    def _hex_to_rgba(self, hex_color: str) -> tuple[int, int, int, int]:
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

    def _parse_metric_config(self, metric_data: dict[str, Any]) -> MetricConfig:
        """Parse a metric configuration from YAML data (no font_path needed)"""
        # Optional independently-positioned label
        label_position = None
        if metric_data.get("label_position") is not None:
            label_position = (
                metric_data["label_position"]["x"],
                metric_data["label_position"]["y"]
            )
        label_color = None
        if metric_data.get("label_color") is not None:
            label_color = self._hex_to_rgba(metric_data["label_color"])

        return MetricConfig(
            name=metric_data["name"],
            label=metric_data.get("label", ""),
            precision=metric_data.get("precision", 2),
            position=(
                metric_data["position"]["x"],
                metric_data["position"]["y"]
            ),
            font_size=metric_data["font_size"],
            color=self._hex_to_rgba(metric_data["color"]),
            format_string=metric_data.get("format_string", "{label}{value}"),
            unit=metric_data.get("unit", ""),
            enabled=metric_data.get("enabled", True),
            label_position=label_position,
            label_font_size=metric_data.get("label_font_size"),
            label_color=label_color,
            font_family=metric_data.get("font_family"),
            bold=metric_data.get("bold", False),
            italic=metric_data.get("italic", False),
            label_font_family=metric_data.get("label_font_family"),
            label_bold=metric_data.get("label_bold", False),
            label_italic=metric_data.get("label_italic", False),
            label_floating=metric_data.get("label_floating", False),
        )

    @staticmethod
    def _label_to_text(mc: MetricConfig) -> TextConfig:
        """Convert a metric's legacy label into a standalone text with its OWN
        style (falls back to the value's style/position only when the label's
        field is absent)."""
        pos = mc.label_position if mc.label_position is not None else mc.position
        return TextConfig(
            text=mc.label,
            position=pos,
            font_size=mc.label_font_size or mc.font_size,
            color=mc.label_color or mc.color,
            enabled=True,
            font_family=mc.label_font_family or mc.font_family,
            bold=mc.label_bold,
            italic=mc.label_italic,
        )

    def _parse_text_config(self, text_data: dict[str, Any]) -> TextConfig:
        """Parse a text configuration from YAML data (no font_path needed)"""
        return TextConfig(
            text=text_data.get("text", ""),
            position=(
                text_data["position"]["x"],
                text_data["position"]["y"]
            ),
            font_size=text_data["font_size"],
            color=self._hex_to_rgba(text_data["color"]),
            enabled=text_data.get("enabled", True),
            font_family=text_data.get("font_family"),
            bold=text_data.get("bold", False),
            italic=text_data.get("italic", False),
        )

    def load_config(self, config_path: str, width: int, height: int,
                     rotation_override: int | None = None,
                     media_endpoint: str = DEFAULT_MEDIA_ENDPOINT) -> DisplayConfig:
        """Load configuration from YAML file. ``rotation_override``, if given,
        is used instead of the file's own ``rotation`` field (see
        :meth:`load_config_from_dict`). ``media_endpoint`` is forwarded to
        :meth:`load_config_from_dict`."""
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, encoding='utf-8') as file:
                yaml_data = yaml.safe_load(file)

            config = self.load_config_from_dict(
                yaml_data, width, height, rotation_override=rotation_override,
                media_endpoint=media_endpoint)
            self.logger.info(f"Configuration loaded successfully from {config_path}")
            return config
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def resolve_resolution_for_rotation(self, width: int, height: int, rotation: int) -> tuple[int, int]:
        """See the module-level :func:`resolve_resolution_for_rotation`."""
        return resolve_resolution_for_rotation(width, height, rotation)

    def load_config_from_dict(self, yaml_data: dict, width: int, height: int,
                               rotation_override: int | None = None,
                               media_endpoint: str = DEFAULT_MEDIA_ENDPOINT) -> DisplayConfig:
        """``rotation_override``, if given, is used instead of the file's own
        ``display.rotation`` — for a caller that already knows the intended
        rotation (e.g. reloading the active config right after a rotation
        click, before it's been saved with the new value) so background/
        foreground paths resolve against the correct, current resolution
        folder instead of the stale on-disk one.

        ``media_endpoint`` is stored on the returned config and used by
        FrameManager for the on-demand bundled-background download (defaults to
        the public endpoint; pass the app's configured one to hit the right
        host). The download itself is performed lazily at read time by
        FrameManager, not here — so merely resolving a config (listing,
        thumbnails) never triggers network I/O."""
        display_data = yaml_data["display"]
        # Parse rotation first: background/foreground paths and output dims are
        # resolved against the rotation-swapped resolution, not the raw device size.
        rotation = (rotation_override if rotation_override is not None
                    else display_data.get("rotation", 0))
        res_width, res_height = self.resolve_resolution_for_rotation(width, height, rotation)

        # Parse metrics configurations
        # Standalone text overlays, plus back-compat: an old metric ``label``
        # (with its own ``label_*`` style) is migrated to an independent text so
        # it no longer shares the metric value's font size.
        texts: list[TextConfig] = []
        for text_data in display_data.get("texts", []) or []:
            if text_data.get("enabled", True):
                texts.append(self._parse_text_config(text_data))

        metrics_configs = []
        if display_data["metrics"]["enabled"]:
            for metric_data in display_data["metrics"]["configs"]:
                if metric_data.get("enabled", True):
                    mc = self._parse_metric_config(metric_data)
                    if mc.label:
                        texts.append(self._label_to_text(mc))
                        mc.label = ""      # rendered as text now, not inline
                    metrics_configs.append(mc)
        # Parse date configuration
        date_config = None
        if display_data["date"]["enabled"]:
            date_config = self._parse_text_config(display_data["date"])
        # Parse time configuration
        time_config = None
        if display_data["time"]["enabled"]:
            time_config = self._parse_text_config(display_data["time"])
        # Parse day-of-week configuration (optional → back-compat with old configs)
        weekday_config = None
        if display_data.get("weekday", {}).get("enabled"):
            weekday_config = self._parse_text_config(display_data["weekday"])
        # Parse foreground configuration
        foreground_path = None
        foreground_position = (0, 0)
        foreground_alpha = 1.0
        if display_data["foreground"]["enabled"]:
            foreground_path = str(display_data["foreground"]["path"]).format(
                resolution=f"{res_width}{res_height}")
            foreground_position = (
                display_data["foreground"]["position"]["x"],
                display_data["foreground"]["position"]["y"]
            )
            foreground_alpha = display_data["foreground"]["alpha"]

        background_path = str(display_data["background"]["path"]).format(
            resolution=f"{res_width}{res_height}")
        background_type = BackgroundType(display_data["background"]["type"])

        config = DisplayConfig(
            output_width=res_width,
            output_height=res_height,
            rotation=rotation,
            background_path=background_path,
            background_type=background_type,
            foreground_image_path=foreground_path,
            foreground_position=foreground_position,
            foreground_alpha=foreground_alpha,
            metrics_configs=metrics_configs,
            date_config=date_config,
            time_config=time_config,
            weekday_config=weekday_config,
            texts=texts,
            media_endpoint=media_endpoint,
        )

        return config
