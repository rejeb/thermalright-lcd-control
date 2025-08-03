# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Themes tab for displaying and selecting theme configurations
"""

import glob
import os
from pathlib import Path
from typing import Dict, Any

import yaml
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QScrollArea, QGridLayout, QPushButton)

from ..widgets.thumbnail_widget import ThumbnailWidget
from ...common.logging_config import get_gui_logger


class ThemesTab(QWidget):
    """Tab widget for displaying theme files"""

    theme_selected = Signal(str)  # Signal emitted with selected theme path

    def __init__(self, config: Dict[str, Any]):
        super().__init__()

        self.logger = get_gui_logger()
        self.config = config
        self.themes_dir = Path(Path.cwd(),config.get('paths', {}).get('themes_dir', './themes'))
        self.thumbnails = []

        self.setup_ui()
        self.load_themes()

    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("Available Themes")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_themes)
        refresh_btn.setMaximumWidth(100)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)

        main_layout.addLayout(header_layout)

        # Scrollable area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.thumbnails_widget = QWidget()
        self.thumbnails_layout = QGridLayout(self.thumbnails_widget)
        self.thumbnails_layout.setSpacing(10)
        self.thumbnails_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll_area.setWidget(self.thumbnails_widget)
        main_layout.addWidget(scroll_area)

    def load_themes(self):
        """Load theme files from themes directory"""
        self.cleanup_thumbnails()

        if not self.themes_dir.exists():
            self.themes_dir.mkdir(parents=True, exist_ok=True)
            return

        # Find all YAML files
        yaml_files = []
        for pattern in ['*.yaml', '*.yml']:
            yaml_files.extend(self.themes_dir.glob(pattern))

        if not yaml_files:
            # Show "no themes" message
            no_themes_label = QLabel("No theme files found in themes directory")
            no_themes_label.setAlignment(Qt.AlignCenter)
            no_themes_label.setStyleSheet("color: #666; font-size: 14px; padding: 50px;")
            self.thumbnails_layout.addWidget(no_themes_label, 0, 0)
            return

        # Sort by modification date (most recent first)
        yaml_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Create thumbnails
        row, col = 0, 0
        max_cols = 8  # Number of thumbnails per row

        for yaml_file in yaml_files:
            try:
                theme_name = self.get_theme_display_name(yaml_file)
                background_path, background_type = self.get_theme_background_info(yaml_file)

                # Determine the actual file path to use for thumbnail
                thumbnail_path = self.get_thumbnail_path(background_path, background_type)

                # Use the thumbnail path for thumbnail generation
                if thumbnail_path and os.path.exists(thumbnail_path):
                    # Use existing ThumbnailWidget which already handles all media types correctly
                    thumbnail_widget = ThumbnailWidget(thumbnail_path, theme_name)
                else:
                    # Create a placeholder thumbnail if no valid background found
                    thumbnail_widget = ThumbnailWidget("", theme_name)

                thumbnail_widget.clicked.connect(
                    lambda path, theme_path=str(yaml_file): self.on_theme_selected(theme_path))

                # Add special styling for theme thumbnails
                thumbnail_widget.setStyleSheet(thumbnail_widget.styleSheet() + """
                    QWidget {
                        border: 2px solid #0078d4;
                    }
                    QWidget:hover {
                        border: 3px solid #005a9e;
                        background-color: #e3f2fd;
                    }
                """)

                self.thumbnails_layout.addWidget(thumbnail_widget, row, col)
                self.thumbnails.append(thumbnail_widget)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            except Exception as e:
                self.logger.error(f"Error loading theme {yaml_file}: {e}")
                continue

    def get_theme_display_name(self, yaml_file: Path) -> str:
        """Get display name for theme file"""
        # Remove extension and clean up filename
        name = yaml_file.stem

        # Replace underscores with spaces and capitalize
        name = name.replace('_', ' ').replace('-', ' ')
        name = ' '.join(word.capitalize() for word in name.split())

        return name

    def get_theme_background_info(self, yaml_file: Path) -> tuple[str, str]:
        """Extract background path and type from theme YAML file"""
        try:
            # Load theme configuration
            with open(yaml_file, 'r', encoding='utf-8') as f:
                theme_config = yaml.safe_load(f)

            display_config = theme_config.get('display', {})
            background_config = display_config.get('background', {})

            # Get background path and type
            background_path = background_config.get('path', "")
            background_type = background_config.get('type', "image")

            return background_path, background_type

        except Exception as e:
            self.logger.error(f"Error reading theme config {yaml_file}: {e}")
            return "", "image"

    def get_thumbnail_path(self, background_path: str, background_type: str) -> str:
        """Get the actual file path to use for thumbnail generation"""
        if not background_path:
            return ""

        # If it's an image_collection, find the first image in the directory
        if background_type == "image_collection":
            if os.path.isdir(background_path):
                return self.get_first_image_from_collection(background_path)
            else:
                self.logger.warning(f"Background path is not a directory: {background_path}")
                return ""
        else:
            # For other types (image, video, gif), use the path directly
            return background_path

    def get_first_image_from_collection(self, collection_path: str) -> str:
        """Get the first image file from an image collection directory"""
        try:
            # Search for all images in the folder (same logic as frame_manager.py)
            image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']
            image_files = []

            for ext in image_extensions:
                image_files.extend(glob.glob(os.path.join(collection_path, ext)))
                image_files.extend(glob.glob(os.path.join(collection_path, ext.upper())))

            if image_files:
                image_files.sort()  # Alphabetical sort
                return image_files[0]  # Return first image
            else:
                self.logger.warning(f"No images found in collection directory: {collection_path}")
                return ""

        except Exception as e:
            self.logger.error(f"Error getting first image from collection {collection_path}: {e}")
            return ""

    def on_theme_selected(self, theme_path: str):
        """Handle theme selection"""
        self.theme_selected.emit(theme_path)

    def get_first_theme_path(self) -> str:
        """Get the path of the first available theme"""
        try:
            if not self.themes_dir.exists():
                return ""

            # Find all YAML files
            yaml_files = []
            for pattern in ['*.yaml', '*.yml']:
                yaml_files.extend(self.themes_dir.glob(pattern))

            if not yaml_files:
                return ""

            # Sort by modification date (most recent first)
            yaml_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            return str(yaml_files[0])  # Return first theme

        except Exception as e:
            self.logger.error(f"Error getting first theme path: {e}")
            return ""

    def auto_load_first_theme(self):
        """Automatically load and emit the first available theme"""
        first_theme_path = self.get_first_theme_path()
        if first_theme_path:
            self.theme_selected.emit(first_theme_path)
            return True
        return False

    def refresh_themes(self):
        """Refresh the themes list"""
        self.load_themes()

    def cleanup_thumbnails(self):
        """Clean up existing thumbnails"""
        for thumbnail in self.thumbnails:
            if hasattr(thumbnail, 'cleanup_video'):
                thumbnail.cleanup_video()
            thumbnail.setParent(None)
            thumbnail.deleteLater()
        self.thumbnails.clear()

        # Clear layout
        while self.thumbnails_layout.count():
            child = self.thumbnails_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def closeEvent(self, event):
        """Handle close event"""
        self.cleanup_thumbnails()
        super().closeEvent(event)
