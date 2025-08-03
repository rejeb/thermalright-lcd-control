# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import os

from PIL import ImageFont

from .utils import _get_default_font_path
from ...common.logging_config import LoggerConfig


class SystemFontManager:
    """Manager for system fonts on Ubuntu/Linux"""

    def __init__(self):
        self.logger = self.logger = LoggerConfig.setup_service_logger()
        self.font_path = _get_default_font_path()
        self._font_cache = {}
        self._system_fonts = {}

    def get_font(self, font_size: int) -> ImageFont.ImageFont:
        """Get a font with caching, supporting both system names and file paths"""

        if font_size not in self._font_cache:
            font = self._load_font(font_size)
            self._font_cache[font_size] = font

        return self._font_cache[font_size]

    def _load_font(self, font_size: int) -> ImageFont.ImageFont:
        """Load a font from system or file path"""
        if not self.font_path:
            return ImageFont.load_default()

        # Check if it's a direct file path
        if os.path.isfile(self.font_path):
            try:
                return ImageFont.truetype(self.font_path, font_size)
            except Exception as e:
                self.logger.warning(f"Could not load font from path {self.font_path}: {e}")
                return ImageFont.load_default(font_size)

        return ImageFont.load_default(font_size)


# Global font manager instance
_font_manager = None


def get_font_manager() -> SystemFontManager:
    """Get the global font manager instance"""
    global _font_manager
    if _font_manager is None:
        _font_manager = SystemFontManager()
    return _font_manager
