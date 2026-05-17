# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import re
from datetime import datetime
from typing import Any

import pyvips

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import (
    MetricConfig,
    TextConfig,
)
from thermalright_lcd_control.device_controller.display.font_manager import (
    get_font_manager,
    pango_font_string,
)


def _parse_color(color) -> tuple[int, int, int, int]:
    """'#RRGGBB[AA]' or (r,g,b[,a]) → (r,g,b,a)."""
    if isinstance(color, str):
        s = color.lstrip("#")
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        a = int(s[6:8], 16) if len(s) >= 8 else 255
        return r, g, b, a
    r, g, b = int(color[0]), int(color[1]), int(color[2])
    a = int(color[3]) if len(color) > 3 else 255
    return r, g, b, a


class TextRenderer:
    """Text rendering manager for images with global font support"""

    def __init__(self):
        self.logger = LoggerConfig.setup_service_logger()
        self.font_manager = get_font_manager()

    def _draw_text(self, overlay: pyvips.Image, position, text: str, color,
                   font_size: int, family, bold: bool, italic: bool) -> pyvips.Image:
        """Composite ``text`` onto ``overlay`` with its ink box top-left at
        ``position``. Returns the new overlay (pyvips images are immutable)."""
        if not text:
            return overlay
        x, y = int(position[0]), int(position[1])
        if x >= overlay.width or y >= overlay.height:
            return overlay
        rf = self.font_manager.get_font(font_size, family, bold, italic)
        kwargs = {"font": pango_font_string(rf, bold, italic), "dpi": 72}
        if rf.path:
            kwargs["fontfile"] = rf.path
        try:
            mask = pyvips.Image.text(text, **kwargs)      # 1-band ink mask
        except pyvips.Error as e:
            self.logger.warning(f"text render failed for {text!r}: {e}")
            return overlay
        r, g, b, a = _parse_color(color)
        colored = mask.new_from_image([r, g, b]).bandjoin(
            (mask * (a / 255.0)).cast("uchar")).copy(interpretation="srgb")
        return vu.overlay_at(overlay, colored, x, y).crop(
            0, 0, overlay.width, overlay.height)

    def _safe_format_value(self, value: Any, format_string: str, metric_name: str) -> str:
        """Safely format a metric value, handling various types and potential errors"""
        if value is None:
            return "N/A"

        try:
            # Try to convert to float if it's a string representation of a number
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    # If conversion fails, return the string as-is
                    return value

            # If it's already a number, format it
            if isinstance(value, (int, float)):
                # Check if the format string contains decimal formatting
                if re.search(r"\.\d+f", format_string):
                    return format_string.format(value=value)
                else:
                    # For other format strings, convert to string first
                    return format_string.format(value=str(value))

            # For any other type, convert to string
            return str(value)

        except Exception as e:
            self.logger.warning(f"Error formatting value {value} for metric {metric_name}: {e}")
            return str(value) if value is not None else "N/A"

    def render_metrics(self, overlay: pyvips.Image, metrics: dict[str, Any] | None,
                       configs: list[MetricConfig]) -> pyvips.Image:
        """Display metrics on the overlay; returns the new overlay."""
        if not metrics or not configs:
            return overlay

        for config in configs:
            if not config.enabled:
                continue

            # Get metric value
            value = metrics.get(config.name)
            if value is None:
                continue

            # The metric label is always rendered as its own element (detached
            # from the value). The value text therefore never embeds it: the
            # ``{label}`` placeholder always resolves to an empty string.
            label_arg = ""

            # Format text safely
            try:
                # Use safe formatting for the value
                formatted_value = self._safe_format_value(value, f"{{value:.{config.precision}f}}" , config.name)

                # If the format string expects a float formatting and we have a numeric value
                if '{value:.0f}' in config.format_string or '{value:.1f}' in config.format_string:
                    try:
                        # Convert to float for proper formatting
                        if isinstance(value, str):
                            numeric_value = float(value)
                        else:
                            numeric_value = float(value)
                        text = config.format_string.format(
                            label=label_arg,
                            value=numeric_value,
                            unit=config.unit
                        )
                    except (ValueError, TypeError):
                        # Fallback: replace format with simple string
                        simple_format = config.format_string.replace('{value:.0f}', '{value}').replace('{value:.1f}',
                                                                                                       '{value}')
                        text = simple_format.format(
                            label=label_arg,
                            value=str(value) if value is not None else "N/A",
                            unit=config.unit
                        )
                else:
                    # Standard formatting
                    text = config.format_string.format(
                        label=label_arg,
                        value=formatted_value,
                        unit=config.unit
                    )

            except Exception as e:
                self.logger.warning(f"Error formatting metric {config.name}: {e}")
                # Fallback to simple display (value only — the label is drawn separately)
                text = f"{value if value is not None else 'N/A'}{config.unit}"

            # Draw value text with this metric's own style. Labels are NOT drawn
            # here — they are independent text overlays (see render_texts), so a
            # label keeps its own font size/color instead of the value's.
            overlay = self._draw_text(overlay, config.position, text, config.color,
                                      config.font_size, config.font_family,
                                      config.bold, config.italic)
        return overlay

    def render_texts(self, overlay: pyvips.Image,
                     texts: list[TextConfig] | None) -> pyvips.Image:
        """Draw standalone text overlays (labels, titles, …), each with its own
        text/position/font/color; returns the new overlay."""
        for config in texts or []:
            if not config.enabled or not config.text:
                continue
            overlay = self._draw_text(overlay, config.position, config.text,
                                      config.color, config.font_size,
                                      config.font_family, config.bold, config.italic)
        return overlay

    def render_date(self, overlay: pyvips.Image, config: TextConfig | None,
                    now: datetime = None) -> pyvips.Image:
        """Display current date formatted as dd/mm; returns the new overlay."""
        if not config or not config.enabled:
            return overlay

        # dd/mm format - use provided datetime to avoid multiple calls
        if now is None:
            now = datetime.now()
        current_date = now.strftime("%d/%m")

        return self._draw_text(overlay, config.position, current_date, config.color,
                               config.font_size, config.font_family,
                               config.bold, config.italic)

    def render_time(self, overlay: pyvips.Image, config: TextConfig | None,
                    now: datetime = None) -> pyvips.Image:
        """Display current time formatted as HH:MM; returns the new overlay."""
        if not config or not config.enabled:
            return overlay

        # HH:MM format - use provided datetime to avoid multiple calls
        if now is None:
            now = datetime.now()
        current_time = now.strftime("%H:%M")

        return self._draw_text(overlay, config.position, current_time, config.color,
                               config.font_size, config.font_family,
                               config.bold, config.italic)

    def render_weekday(self, overlay: pyvips.Image, config: TextConfig | None,
                       now: datetime = None) -> pyvips.Image:
        """Display the current day of week (e.g. "Monday"); returns the new overlay."""
        if not config or not config.enabled:
            return overlay

        if now is None:
            now = datetime.now()
        current_weekday = now.strftime("%A")

        return self._draw_text(overlay, config.position, current_weekday, config.color,
                               config.font_size, config.font_family,
                               config.bold, config.italic)

