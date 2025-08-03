# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple


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
    position: Tuple[int, int] = (0, 0)  # (x, y)
    font_size: int = 20
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA
    enabled: bool = True


@dataclass
class MetricConfig:
    """Configuration for metric display"""
    name: str
    label: str = ""
    position: Tuple[int, int] = (0, 0)
    font_size: int = 16
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    format_string: str = "{label}{value}"
    unit: str = ""
    enabled: bool = True
    def format_label(self):
        return f"{self.label}: " if self.label else ""


@dataclass
class DisplayConfig:
    """Complete display configuration"""
    # Background (required)
    background_path: str
    background_type: BackgroundType

    # Output dimensions
    output_width: int = 320
    output_height: int = 240

    # Global font configuration (applies to all text elements)
    global_font_path: Optional[str] = None

    # Foreground image (optional)
    foreground_image_path: Optional[str] = None
    foreground_position: Tuple[int, int] = (0, 0)
    foreground_alpha: float = 1.0  # 0.0 = transparent, 1.0 = opaque

    # Metrics configuration
    metrics_configs: List[MetricConfig] = None

    # Date configuration
    date_config: Optional[TextConfig] = None

    # Time configuration
    time_config: Optional[TextConfig] = None

    def __post_init__(self):
        if self.metrics_configs is None:
            self.metrics_configs = []
