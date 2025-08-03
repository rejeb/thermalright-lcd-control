# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Tab widget for displaying media files with thumbnails
"""

import shutil
import uuid
from pathlib import Path
from typing import Optional

from PIL.ImageQt import QPixmap
from PySide6.QtCore import Qt, QSize
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap, QIcon  # Ajouter QIcon ici
from PySide6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
    QLabel,
    QFileDialog,
    QMessageBox
)
from PySide6.QtWidgets import (QScrollArea,
                               QGridLayout, QSpacerItem, QSizePolicy, QHBoxLayout)

from ..widgets.thumbnail_widget import ThumbnailWidget
from ...common.logging_config import get_gui_logger


class MediaTab(QWidget):
    """Tab widget for media files with thumbnail grid"""
    thumbnail_clicked = Signal(str)  # Signal emitted when thumbnail is clicked
    media_added = Signal(str)  # Signal emitted when new media is added
    collection_created = Signal(str)

    # Prefix to identify user-added files
    USER_ADDED_IMG_PREFIX = "user_"
    USER_ADDED_COL_PREFIX = "collection_"

    def __init__(self, media_dir, config, tab_name="Media Files"):
        super().__init__()
        self.logger = get_gui_logger()
        self.media_dir = media_dir
        self.config = config
        self.tab_name = tab_name
        self.thumbnails = []  # Track thumbnails for cleanup
        self.setup_ui()
        self.load_media_files()

    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)

        # Only show add media button for backgrounds tab
        if self.tab_name.lower() == "backgrounds":
            # Top section with single add media button
            top_layout = QHBoxLayout()

            # Single button for adding media (single or multiple)
            self.add_media_btn = QPushButton(f"Add Media")
            self.add_media_btn.clicked.connect(self.add_media_files)
            self.add_media_btn.setMaximumWidth(150)

            top_layout.addWidget(self.add_media_btn)
            top_layout.addStretch()  # Push button to the left

            layout.addLayout(top_layout)

        # Scroll area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container widget for thumbnails grid
        self.thumbnails_widget = QWidget()
        self.thumbnails_layout = QGridLayout(self.thumbnails_widget)
        self.thumbnails_layout.setSpacing(10)
        self.thumbnails_layout.setContentsMargins(10, 10, 10, 10)

        # Configure scroll area
        scroll_area.setWidget(self.thumbnails_widget)

        layout.addWidget(scroll_area)

    def add_media_files(self):
        """Open file dialog to add single or multiple media files"""
        # Only allow adding media for backgrounds tab
        if self.tab_name.lower() != "backgrounds":
            return

        try:
            supported_extensions = self.get_supported_extensions()

            # Create file filter based on supported extensions
            filter_str = "Media files ("
            filter_str += " ".join([f"*{ext}" for ext in sorted(supported_extensions)])
            filter_str += ")"

            # Open file dialog for multiple selection
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                f"Select one or more media files for {self.tab_name}",
                "",
                filter_str
            )

            if file_paths:
                # Check if multiple files selected for collection creation
                if len(file_paths) > 1:
                    self.create_collection_from_files(file_paths)
                else:
                    # Single file - use existing logic
                    file_path = file_paths[0]

                    # Validate file extension
                    file_extension = Path(file_path).suffix.lower()
                    if file_extension not in supported_extensions:
                        QMessageBox.warning(
                            self,
                            "Unsupported Format",
                            f"Format {file_extension} is not supported for {self.tab_name}.\n\n"
                            f"Supported formats: {', '.join(sorted(supported_extensions))}"
                        )
                        return

                    # Copy single file
                    self.copy_media_file(file_path)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error adding media:\n{str(e)}"
            )

    def create_collection_from_files(self, file_paths):
        """Create a collection from selected files"""
        try:
            supported_extensions = self.get_supported_extensions()

            # Validate all files
            invalid_files = []
            for file_path in file_paths:
                file_extension = Path(file_path).suffix.lower()
                if file_extension not in supported_extensions:
                    invalid_files.append(Path(file_path).name)

            if invalid_files:
                QMessageBox.warning(
                    self,
                    "Unsupported formats",
                    "The following files have unsupported formats and will be ignored:\n" +
                    "\n".join(invalid_files[:5]) +
                    (f"\n... and {len(invalid_files) - 5} others" if len(invalid_files) > 5 else "")
                )
                # Filter out invalid files
                file_paths = [fp for fp in file_paths if Path(fp).suffix.lower() in supported_extensions]

            if not file_paths:
                return

            # Create unique collection name
            collection_name = f"collection_{uuid.uuid4().hex[:8]}"
            collection_dir = Path(self.media_dir) / collection_name
            collection_dir.mkdir(exist_ok=True)

            # Copy each file to collection directory
            copied_files = []
            for file_path in file_paths:
                source_path = Path(file_path)
                dest_path = self.get_unique_filename(collection_dir, source_path.name)

                shutil.copy2(source_path, dest_path)
                copied_files.append(dest_path)
                self.logger.info(f"Copied {source_path} to {dest_path}")

            # Show success message
            QMessageBox.information(
                self,
                "Created collection",
                f"Collection created successfully with {len(copied_files)} files:\n{collection_dir.name}"
            )

            # Reload media files and emit signals
            self.reload_media_files()
            self.collection_created.emit(str(collection_dir))

        except Exception as e:
            self.logger.error(f"Error creating collection:\n{str(e)}")
            QMessageBox.critical(
                self,
                "Erreur",
                f"Error creating collection:\n{str(e)}"
            )

    def get_supported_extensions(self):
        """Get supported extensions based on tab type"""
        supported_formats = self.config.get('supported_formats', {})

        if self.tab_name.lower() == "backgrounds":
            # Background supports all formats
            image_extensions = set(supported_formats.get('images', []))
            video_extensions = set(supported_formats.get('videos', []))
            gif_extensions = set(supported_formats.get('gifs', []))
            return image_extensions | video_extensions | gif_extensions
        elif self.tab_name.lower() == "foregrounds":
            # Foreground supports only images (but no adding functionality)
            return set(supported_formats.get('images', []))
        else:
            # Default to all formats
            image_extensions = set(supported_formats.get('images', []))
            video_extensions = set(supported_formats.get('videos', []))
            gif_extensions = set(supported_formats.get('gifs', []))
            return image_extensions | video_extensions | gif_extensions

    def create_collection_thumbnail(self, collection_dir) -> Optional[QWidget]:
        """Add thumbnail for collection directory to the layout"""
        try:

            image_files = [f for f in collection_dir.iterdir()
                           if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']]

            if not image_files:
                return None

            first_image = image_files[0]

            thumbnail_btn = QPushButton()
            thumbnail_btn.setFixedSize(100, 100)
            thumbnail_btn.setStyleSheet("border: 2px solid gray; border-radius: 5px;")

            pixmap = QPixmap(str(first_image))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumbnail_btn.setIcon(QIcon(scaled_pixmap))
                thumbnail_btn.setIconSize(QSize(96, 96))

            # Nom d'affichage pour la collection
            display_name = f"Collection ({len(image_files)} images)"
            thumbnail_btn.setToolTip(f"{display_name}\nPath: {collection_dir}")

            # Connecter le clic pour émettre le chemin du dossier
            thumbnail_btn.clicked.connect(
                lambda checked, path=str(collection_dir): self.thumbnail_clicked.emit(path)
            )

            # Ajouter au layout avec le nom
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.addWidget(thumbnail_btn)

            name_label = QLabel(display_name)
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setWordWrap(True)
            name_label.setMaximumWidth(100)
            container_layout.addWidget(name_label)

            return container

        except Exception as e:
            self.config.logger.warning(f"Could not create thumbnail for collection {collection_dir}: {e}")

    def get_unique_filename(self, dest_dir, original_name):
        """Get a unique filename with user prefix, avoiding conflicts"""
        file_path = Path(original_name)
        name_without_ext = file_path.stem
        extension = file_path.suffix

        # Start with the user prefix
        base_name = f"{self.USER_ADDED_IMG_PREFIX}{name_without_ext}"
        new_name = f"{base_name}{extension}"
        dest_path = dest_dir / new_name

        # If file already exists, add a counter
        counter = 1
        while dest_path.exists():
            new_name = f"{base_name}_{counter}{extension}"
            dest_path = dest_dir / new_name
            counter += 1

        return dest_path

    def copy_media_file(self, source_path):
        """Copy media file to the appropriate directory"""
        try:
            source_file = Path(source_path)

            # Create destination directory if it doesn't exist
            dest_dir = Path(self.media_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Get unique filename with user prefix
            dest_path = self.get_unique_filename(dest_dir, source_file.name)

            # Copy the file
            shutil.copy2(source_path, dest_path)

            # Show success message
            QMessageBox.information(
                self,
                "Media Added",
                f"File '{source_file.name}' was successfully added as '{dest_path.name}'."
            )

            # Reload media files to show the new file
            self.reload_media_files()

            # Automatically apply the new media
            self.auto_apply_new_media(str(dest_path))

            # Emit signal for other components
            self.media_added.emit(str(dest_path))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Copy Error",
                f"Unable to copy file:\n{str(e)}"
            )

    def auto_apply_new_media(self, file_path):
        """Automatically apply the newly added media"""
        try:
            self.logger.debug(f"Auto-applying new media: {file_path} in tab {self.tab_name}")

            # Emit the thumbnail clicked signal to apply the media
            self.thumbnail_clicked.emit(file_path)

            # Log the action
            if self.tab_name.lower() == "backgrounds":
                self.logger.debug(f"New background automatically applied: {Path(file_path).name}")

        except Exception as e:
            self.logger.error(f"Warning: Could not auto-apply new media: {e}")

    def is_user_added_file(self, file_path):
        """Check if a file was added by the user based on filename prefix"""
        return Path(file_path).name.startswith(self.USER_ADDED_IMG_PREFIX) or Path(file_path).name.startswith(
            self.USER_ADDED_COL_PREFIX)

    def sort_files_user_first(self, files):
        """Sort files with user-added files first (by prefix), then alphabetically"""
        try:
            # Separate user-added files from regular files
            user_files = []
            regular_files = []

            for file_path in files:
                if self.is_user_added_file(file_path):
                    user_files.append(file_path)
                else:
                    regular_files.append(file_path)

            # Sort each group alphabetically
            user_files.sort(key=lambda x: x.name.lower())
            regular_files.sort(key=lambda x: x.name.lower())

            # Return user files first, then regular files
            return user_files + regular_files

        except Exception as e:
            self.logger.warning(f"Warning: Could not sort files: {e}")
            # Fallback to name sorting
            return sorted(files, key=lambda x: x.name.lower())

    def get_display_name(self, file_path):
        """Get display name for thumbnail (remove user prefix if present)"""
        name = Path(file_path).name
        if name.startswith(self.USER_ADDED_IMG_PREFIX):
            # Remove the prefix for display
            name_without_prefix = name[len(self.USER_ADDED_IMG_PREFIX):]
            return name_without_prefix
        return name

    def reload_media_files(self):
        """Reload media files and refresh the interface"""
        # Clear existing thumbnails
        self.cleanup_thumbnails()

        # Clear the layout
        for i in reversed(range(self.thumbnails_layout.count())):
            child = self.thumbnails_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()

        # Reload files
        self.load_media_files()

    def load_media_files(self):
        """Load media files from configured directory"""
        media_dir = Path(self.media_dir)
        supported_extensions = self.get_supported_extensions()

        try:
            if media_dir.exists() and media_dir.is_dir():
                files = []
                for file_path in media_dir.iterdir():
                    if file_path.is_dir() and file_path.name.startswith('collection_'):
                        files.append(file_path)
                    elif file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                        files.append(file_path)

                if not files:
                    # No media files found
                    supported_formats = self.config.get('supported_formats', {})
                    if self.tab_name.lower() == "backgrounds":
                        format_info = (f"Images: {', '.join(sorted(supported_formats.get('images', [])))}\n" +
                                       f"Vidéos: {', '.join(sorted(supported_formats.get('videos', [])))}\n" +
                                       f"GIFs: {', '.join(sorted(supported_formats.get('gifs', [])))}")
                    else:
                        format_info = f"Images: {', '.join(sorted(supported_formats.get('images', [])))}"

                    error_label = QLabel(f"Aucun média trouvé dans:\n{media_dir}\n\nFormats supportés:\n{format_info}")
                    error_label.setAlignment(Qt.AlignCenter)
                    error_label.setStyleSheet("color: orange; font-size: 12px;")
                    self.thumbnails_layout.addWidget(error_label, 0, 0)
                    return

                # Sort files with user-added files first
                files = self.sort_files_user_first(files)

                self.logger.debug(f"Found {len(files)} media files in {media_dir} (sorted with user-added first)")

                # Create thumbnails in grid (4 columns)
                row, col = 0, 0
                max_cols = 8

                for i, file_path in enumerate(files):
                    if file_path.is_dir():
                        collection_widget = self.create_collection_thumbnail(file_path)
                        self.thumbnails_layout.addWidget(collection_widget, row, col)
                    else:
                        # Use display name (without prefix) for thumbnail
                        display_name = self.get_display_name(file_path)
                        thumbnail = ThumbnailWidget(str(file_path), display_name)
                        thumbnail.clicked.connect(self.on_thumbnail_clicked)

                        # Track thumbnails for cleanup
                        self.thumbnails.append(thumbnail)

                        # Add visual indicator for user-added files
                        if self.is_user_added_file(file_path):
                            # Add a subtle visual indicator for user-added files
                            thumbnail.setStyleSheet("""
                                QFrame {
                                    border: 2px solid #4CAF50;
                                    border-radius: 4px;
                                }
                            """)

                        self.thumbnails_layout.addWidget(thumbnail, row, col)

                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1

                # Add spacer to push everything to the top
                spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
                self.thumbnails_layout.addItem(spacer, row + 1, 0, 1, max_cols)

            else:
                # Directory doesn't exist
                error_label = QLabel(f"Répertoire média introuvable:\n{media_dir}\n\n" +
                                     f"Veuillez vérifier le paramètre '{self.tab_name.lower()}_dir' dans votre fichier de configuration.")
                error_label.setAlignment(Qt.AlignCenter)
                error_label.setStyleSheet("color: red; font-size: 14px;")
                self.thumbnails_layout.addWidget(error_label, 0, 0)

        except Exception as e:
            error_label = QLabel(f"Erreur lors du chargement des médias:\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red; font-size: 14px;")
            self.thumbnails_layout.addWidget(error_label, 0, 0)
            self.logger.error(f"Exception in load_media_files for {self.tab_name}: {e}")

    def on_thumbnail_clicked(self, file_path):
        """Handle thumbnail click and emit signal"""
        self.thumbnail_clicked.emit(file_path)

    def cleanup_thumbnails(self):
        """Clean up all thumbnail resources"""
        for thumbnail in self.thumbnails:
            thumbnail.cleanup_video()
        self.thumbnails.clear()

    def closeEvent(self, event):
        """Cleanup on close"""
        self.cleanup_thumbnails()
        super().closeEvent(event)
