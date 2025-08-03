# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Thumbnail widget for displaying media file previews
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QMovie, QImage
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QStackedWidget

from ...common.logging_config import get_gui_logger


class ThumbnailWidget(QWidget):
    """Custom widget to display a thumbnail with filename"""
    clicked = Signal(str)  # Signal emitted with file path

    def __init__(self, file_path, file_name):
        super().__init__()
        self.logger = get_gui_logger()
        self.file_path = file_path
        self.file_name = file_name
        self.media_player = None
        self.audio_output = None
        self.is_video = False

        self.setFixedSize(120, 100)
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            QWidget:hover {
                background-color: #f0f0f0;
                border: 2px solid #0078d4;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Container for thumbnail content
        self.content_container = QWidget()
        self.content_container.setFixedSize(110, 70)

        # Stack widget to switch between label and video
        self.content_stack = QStackedWidget(self.content_container)
        self.content_stack.setGeometry(0, 0, 110, 70)

        # Label for images and gifs
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(110, 70)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                color: #333;
            }
        """)

        # Video widget for videos
        self.video_widget = QVideoWidget()
        self.video_widget.setFixedSize(110, 70)
        self.video_widget.setStyleSheet("""
            QVideoWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)

        # Add to stack
        self.content_stack.addWidget(self.thumb_label)   # Index 0
        self.content_stack.addWidget(self.video_widget)  # Index 1
        self.content_stack.setCurrentIndex(0)  # Start with label

        # Label for filename
        self.name_label = QLabel(file_name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                font-size: 10px;
                color: #333;
            }
        """)

        layout.addWidget(self.content_container)
        layout.addWidget(self.name_label)

        # Generate thumbnail
        self.generate_thumbnail()

    def generate_thumbnail(self):
        """Generate thumbnail based on file type"""
        try:
            file_path = Path(self.file_path)
            extension = file_path.suffix.lower()

            if extension in {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}:
                self.create_image_thumbnail()
            elif extension == '.gif':
                self.create_gif_thumbnail()
            elif extension in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.m4v', '.webm'}:
                self.create_video_thumbnail()
            else:
                self.content_stack.setCurrentIndex(0)
                self.thumb_label.setText("?")

        except Exception as e:
            self.content_stack.setCurrentIndex(0)
            self.thumb_label.setText("Error")
            self.logger.error(f"Thumbnail generation error for {self.file_path}: {e}")

    def create_image_thumbnail(self):
        """Create thumbnail for an image"""
        self.content_stack.setCurrentIndex(0)

        pixmap = QPixmap(self.file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(110, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb_label.setPixmap(scaled)
        else:
            self.thumb_label.setText("Image\nUnavailable")

    def create_gif_thumbnail(self):
        """Create thumbnail for a GIF"""
        self.content_stack.setCurrentIndex(0)

        try:
            movie = QMovie(self.file_path)
            if movie.isValid():
                movie.setScaledSize(QSize(110, 70))
                self.thumb_label.setMovie(movie)
                movie.start()
            else:
                self.thumb_label.setText("GIF\nUnavailable")
        except Exception as e:
            self.thumb_label.setText("GIF\nError")
            self.logger.error(f"GIF thumbnail error: {e}")

    def create_video_thumbnail(self):
        """Create static thumbnail for a video using OpenCV"""
        self.content_stack.setCurrentIndex(0)  # Use label

        try:
            import cv2

            # Open video file
            cap = cv2.VideoCapture(self.file_path)

            if cap.isOpened():
                # Get total frame count
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                # Seek to 10% of video duration
                if frame_count > 10:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count // 10)

                # Read frame
                ret, frame = cap.read()

                if ret:
                    # Convert BGR to RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                    # Convert to QImage
                    height, width, channel = rgb_frame.shape
                    bytes_per_line = 3 * width
                    q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

                    # Convert to QPixmap and scale
                    pixmap = QPixmap.fromImage(q_image)
                    scaled = pixmap.scaled(110, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.thumb_label.setPixmap(scaled)
                else:
                    raise Exception("Could not read frame")

                cap.release()

            else:
                raise Exception("Could not open video file")

        except ImportError:
            self.logger.error("OpenCV not available, using text thumbnail for video")
            self.thumb_label.setText("📹\nVIDEO")
            self.thumb_label.setStyleSheet("""
                QLabel {
                    background-color: #2c3e50;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    color: white;
                    font-size: 14px;
                }
            """)
        except Exception as e:
            self.logger.error(f"Video thumbnail error: {e}")
            # Fallback to text icon
            self.thumb_label.setText("📹\nVIDEO")
            self.thumb_label.setStyleSheet("""
                QLabel {
                    background-color: #2c3e50;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    color: white;
                    font-size: 14px;
                }
            """)

    def mousePressEvent(self, event):
        """Handle click on thumbnail"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def cleanup_video(self):
        """Clean up video resources"""
        if self.media_player:
            self.media_player.stop()
            if hasattr(self.media_player, 'mediaStatusChanged'):
                try:
                    self.media_player.mediaStatusChanged.disconnect()
                except:
                    pass
            self.media_player.setVideoOutput(None)
            self.media_player = None
        if self.audio_output:
            self.audio_output = None

    def __del__(self):
        """Cleanup when widget is destroyed"""
        self.cleanup_video()