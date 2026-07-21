# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Preview edit-state holder.

Since Part 2 the GUI preview reads the controller's shared base frame; this class
no longer renders. It just holds the user's current edit-state (background /
foreground paths, rotation, opacity, dimensions) which ``ConfigGenerator`` turns
into a DisplayConfig and which the backend publishes live to the engine."""

from pathlib import Path

from thermalright_lcd_control.device_controller.display.config import BackgroundType


class PreviewManager:
    def __init__(self, config, preview_label=None, text_style=None):
        self.config = config
        self.preview_label = preview_label
        self.text_style = text_style

        self.preview_width = 320
        self.preview_height = 240
        self.current_background_path = None
        self.current_foreground_path = None
        self.foreground_opacity = 0.5
        self.current_rotation = 0

    def set_device_dimensions(self, width: int, height: int):
        self.preview_width = width
        self.preview_height = height

    def initialize_default_background(self, backgrounds_dir: str):
        """Pick the first supported background file as the current one."""
        backgrounds_path = Path(backgrounds_dir)
        if not backgrounds_path.exists():
            self.current_background_path = None
            return
        supported_formats = self.config.get('supported_formats', {})
        supported_extensions = (set(supported_formats.get('images', [])) |
                                set(supported_formats.get('videos', [])) |
                                set(supported_formats.get('gifs', [])))
        for file_path in backgrounds_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                self.current_background_path = str(file_path)
                return
        self.current_background_path = None

    def determine_background_type(self, file_path):
        if not file_path:
            return BackgroundType.IMAGE
        if Path(file_path).is_dir():
            return BackgroundType.IMAGE_COLLECTION
        extension = Path(file_path).suffix.lower()
        supported_formats = self.config.get('supported_formats', {})
        if extension in supported_formats.get('videos', []):
            return BackgroundType.VIDEO
        elif extension in supported_formats.get('gifs', []):
            return BackgroundType.GIF
        return BackgroundType.IMAGE

    def set_background(self, file_path: str):
        self.current_background_path = file_path

    def set_foreground(self, file_path: str):
        self.current_foreground_path = file_path

    def set_foreground_opacity(self, opacity: float):
        self.foreground_opacity = opacity

    def set_rotation(self, rotation: int):
        self.current_rotation = rotation

    def clear_foreground(self):
        self.current_foreground_path = None

    def clear_all(self, backgrounds_dir: str):
        self.current_foreground_path = None
        self.current_background_path = None
        self.initialize_default_background(backgrounds_dir)

    def cleanup(self):
        pass
