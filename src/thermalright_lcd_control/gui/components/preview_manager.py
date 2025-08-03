# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Preview manager for display generation and frame updates"""

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QLabel

from ...device_controller.display.config import DisplayConfig, BackgroundType
from ...device_controller.display.generator import DisplayGenerator


class PreviewManager:
    """Manages display generation and frame updates for preview"""

    def __init__(self, config, preview_label: QLabel, text_style):
        self.config = config
        self.preview_label = preview_label
        self.text_style = text_style

        # Display properties
        self.preview_width = 320
        self.preview_height = 240
        self.current_background_path = None
        self.current_foreground_path = None
        self.foreground_opacity = 0.5

        # Components
        self.display_generator = None
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview_frame)

    def set_device_dimensions(self, width: int, height: int):
        """Set preview dimensions from detected device"""
        self.preview_width = width
        self.preview_height = height

    def initialize_default_background(self, backgrounds_dir: str):
        """Initialize with the first background file found"""
        try:
            backgrounds_path = Path(backgrounds_dir)
            if not backgrounds_path.exists():
                self.preview_label.setText("Background directory\nnot found")
                return

            supported_formats = self.config.get('supported_formats', {})
            supported_extensions = (set(supported_formats.get('images', [])) |
                                    set(supported_formats.get('videos', [])) |
                                    set(supported_formats.get('gifs', [])))

            for file_path in backgrounds_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    self.current_background_path = str(file_path)
                    self.create_display_generator()
                    return

            self.preview_label.setText("No background files\nfound")
        except Exception as e:
            self.preview_label.setText(f"Error loading\nbackground: {e}")

    def determine_background_type(self, file_path):
        """Determine BackgroundType from file extension"""
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

    def create_display_generator(self):
        """Create or recreate DisplayGenerator with current settings"""
        if not self.current_background_path:
            return

        try:
            display_config = DisplayConfig(
                background_path=self.current_background_path,
                background_type=self.determine_background_type(self.current_background_path),
                output_width=self.preview_width,
                output_height=self.preview_height,
                global_font_path=self.text_style.font_family,
                foreground_image_path=self.current_foreground_path,
                foreground_position=(0, 0),
                foreground_alpha=self.foreground_opacity
            )

            if self.display_generator:
                self.display_generator.cleanup()

            self.display_generator = DisplayGenerator(display_config)
            self.update_preview_frame()
        except Exception as e:
            self.preview_label.setText(f"Error creating\nDisplayGenerator:\n{str(e)}")

    def update_preview_frame(self):
        """Update preview with next frame from DisplayGenerator"""
        if not self.display_generator:
            return

        try:
            pil_image, duration = self.display_generator.get_frame_with_duration()
            qpixmap = self.pil_image_to_qpixmap(pil_image)

            if qpixmap and not qpixmap.isNull():
                self.preview_label.setPixmap(qpixmap)
            else:
                self.preview_label.setText("Error converting\nimage")

            next_update_ms = max(int(duration * 1000), 33)
            self.preview_timer.setSingleShot(True)
            self.preview_timer.start(next_update_ms)
        except Exception as e:
            self.preview_label.setText(f"Error updating\npreview:\n{str(e)}")

    def pil_image_to_qpixmap(self, pil_image):
        """Convert PIL Image to QPixmap"""
        try:
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            width, height = pil_image.size
            image_data = pil_image.tobytes("raw", "RGB")
            qimage = QImage(image_data, width, height, QImage.Format_RGB888)
            return QPixmap.fromImage(qimage)
        except Exception:
            return None

    def set_background(self, file_path: str):
        """Set background media"""
        self.current_background_path = file_path
        self.create_display_generator()

    def set_foreground(self, file_path: str):
        """Set foreground media"""
        self.current_foreground_path = file_path
        self.create_display_generator()

    def set_foreground_opacity(self, opacity: float):
        """Set foreground opacity (0.0 to 1.0)"""
        self.foreground_opacity = opacity
        self.create_display_generator()

    def clear_background(self, backgrounds_dir: str):
        """Clear background media"""
        self.current_background_path = None
        self.initialize_default_background(backgrounds_dir)

    def clear_foreground(self):
        """Clear foreground media"""
        self.current_foreground_path = None
        self.create_display_generator()

    def clear_all(self, backgrounds_dir: str):
        """Clear all media"""
        self.current_foreground_path = None
        self.current_background_path = None
        self.initialize_default_background(backgrounds_dir)

    def cleanup(self):
        """Cleanup resources"""
        self.preview_timer.stop()
        if self.display_generator:
            self.display_generator.cleanup()
