# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from datetime import datetime
from typing import Optional, List, Dict, Any

from PIL import ImageDraw, ImageFont

from .config import TextConfig, MetricConfig, DisplayConfig
from ...common.logging_config import LoggerConfig

# Import font manager from current package
try:
    from .font_manager import get_font_manager
except ImportError:
    # Fallback if font_manager is not available
    class FallbackFontManager:
        def get_font(self, font_size: int) -> ImageFont.ImageFont:
            return ImageFont.load_default(font_size)


    def get_font_manager():
        return FallbackFontManager()


class TextRenderer:
    """Text rendering manager for images with global font support"""

    def __init__(self, display_config: DisplayConfig):
        self.logger = LoggerConfig.setup_service_logger()
        self.font_manager = get_font_manager()
        self._font_cache = {}

    def _get_font(self, font_size: int) -> ImageFont.ImageFont:
        return self.font_manager.get_font(font_size)

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
                if '.0f' in format_string or '.1f' in format_string or '.2f' in format_string:
                    return format_string.format(value=value)
                else:
                    # For other format strings, convert to string first
                    return format_string.format(value=str(value))

            # For any other type, convert to string
            return str(value)

        except Exception as e:
            self.logger.warning(f"Error formatting value {value} for metric {metric_name}: {e}")
            return str(value) if value is not None else "N/A"

    def render_metrics(self, draw: ImageDraw.Draw, metrics: Optional[Dict[str, Any]],
                       configs: List[MetricConfig]):
        """Display metrics on the image"""
        if not metrics or not configs:
            return

        for config in configs:
            if not config.enabled:
                continue

            # Get metric value
            value = metrics.get(config.name)
            if value is None:
                continue

            # Format text safely
            try:
                # Use safe formatting for the value
                formatted_value = self._safe_format_value(value, "{value}", config.name)

                # If the format string expects a float formatting and we have a numeric value
                if '{value:.0f}' in config.format_string or '{value:.1f}' in config.format_string:
                    try:
                        # Convert to float for proper formatting
                        if isinstance(value, str):
                            numeric_value = float(value)
                        else:
                            numeric_value = float(value)
                        text = config.format_string.format(
                            label=config.format_label(),
                            value=numeric_value,
                            unit=config.unit
                        )
                    except (ValueError, TypeError):
                        # Fallback: replace format with simple string
                        simple_format = config.format_string.replace('{value:.0f}', '{value}').replace('{value:.1f}',
                                                                                                       '{value}')
                        text = simple_format.format(
                            label=config.label,
                            value=str(value) if value is not None else "N/A",
                            unit=config.unit
                        )
                else:
                    # Standard formatting
                    text = config.format_string.format(
                        label=config.format_label(),
                        value=formatted_value,
                        unit=config.unit
                    )

            except Exception as e:
                self.logger.warning(f"Error formatting metric {config.name}: {e}")
                # Fallback to simple display
                text = f"{config.label}: {value if value is not None else 'N/A'}{config.unit}"

            # Get font using global font configuration
            font = self._get_font(config.font_size)

            # Draw text
            draw.text(config.position, text, fill=config.color, font=font)

    def render_date(self, draw: ImageDraw.Draw, config: Optional[TextConfig]):
        """Display current date formatted as dd/mm"""
        if not config or not config.enabled:
            return

        # dd/mm format
        current_date = datetime.now().strftime("%d/%m")

        # Get font using global font configuration
        font = self._get_font(config.font_size)

        # Draw text
        draw.text(config.position, current_date, fill=config.color, font=font)

    def render_time(self, draw: ImageDraw.Draw, config: Optional[TextConfig]):
        """Display current time formatted as HH:MM"""
        if not config or not config.enabled:
            return

        # HH:MM format
        current_time = datetime.now().strftime("%H:%M")

        # Get font using global font configuration
        font = self._get_font(config.font_size)

        # Draw text
        draw.text(config.position, current_time, fill=config.color, font=font)

    def render_custom_text(self, draw: ImageDraw.Draw, config: TextConfig):
        """Display custom text"""
        if not config.enabled or not config.text:
            return

        # Get font using global font configuration
        font = self._get_font(config.font_size)

        # Draw text
        draw.text(config.position, config.text, fill=config.color, font=font)
