# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from dataclasses import dataclass
from enum import Enum


class BackgroundType(Enum):
    """Supported background types"""
    IMAGE = "image"
    GIF = "gif"
    VIDEO = "video"
    IMAGE_COLLECTION = "image_collection"


@dataclass
class TextConfig:
    """Configuration for text display"""
    text: str = ""
    position: tuple[int, int] = (0, 0)  # (x, y)
    font_size: int = 20
    color: tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA
    enabled: bool = True

    # Optional font styling. Absent → historical default font.
    font_family: str | None = None
    bold: bool = False
    italic: bool = False


@dataclass
class MetricConfig:
    """Configuration for metric display"""
    name: str
    label: str = ""
    position: tuple[int, int] = (0, 0)
    font_size: int = 16
    color: tuple[int, int, int, int] = (255, 255, 255, 255)
    format_string: str = "{label}{value}"
    unit: str = ""
    enabled: bool = True
    precision: int = 2

    # Optional independently-positioned label. When ``label_position`` is set,
    # the label is drawn on its own (its position / style) and the value is
    # rendered without the inline label. ``None`` → legacy inline behaviour.
    label_position: tuple[int, int] | None = None
    label_font_size: int | None = None
    label_color: tuple[int, int, int, int] | None = None

    # Optional font styling for the value. Absent → historical default font.
    font_family: str | None = None
    bold: bool = False
    italic: bool = False

    # Optional font styling for the detached label (independent of the value).
    label_font_family: str | None = None
    label_bold: bool = False
    label_italic: bool = False

    # GUI : le label détaché peut être déplacé librement (mode floating).
    label_floating: bool = False


@dataclass
class DisplayConfig:
    """Complete display configuration"""
    # Background (required)
    background_path: str
    background_type: BackgroundType

    # Output dimensions
    output_width: int = 320
    output_height: int = 240

    # Display rotation (0, 90, 180, 270 degrees)
    rotation: int = 0

    # Global font configuration (applies to all text elements)
    global_font_path: str | None = None

    # Foreground image (optional)
    foreground_image_path: str | None = None
    foreground_position: tuple[int, int] = (0, 0)
    foreground_alpha: float = 1.0  # 0.0 = transparent, 1.0 = opaque

    # Metrics configuration
    metrics_configs: list[MetricConfig] = None

    # Date configuration
    date_config: TextConfig | None = None

    # Time configuration
    time_config: TextConfig | None = None

    # Day-of-week configuration (rendered as the weekday name, e.g. "Monday")
    weekday_config: TextConfig | None = None

    # Standalone text overlays (labels, titles, …) — rendered independently of
    # metrics, each with its own text/position/font/color.
    texts: list[TextConfig] = None

    # Endpoint for the on-demand bundled-background download performed lazily by
    # FrameManager. None → the module default (asset_download.DEFAULT_MEDIA_ENDPOINT).
    media_endpoint: str | None = None

    def __post_init__(self):
        if self.metrics_configs is None:
            self.metrics_configs = []
        if self.texts is None:
            self.texts = []
