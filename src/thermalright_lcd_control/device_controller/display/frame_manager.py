# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import glob
import logging
import os
import threading
import time
from typing import Tuple

from PIL import Image, ImageSequence

from .config import BackgroundType, DisplayConfig
from ..metrics.cpu_metrics import CpuMetrics
from ..metrics.gpu_metrics import GpuMetrics

# Try to import OpenCV for video support
try:
    import cv2

    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


class FrameManager:
    """Frame manager with real-time metrics updates"""

    # Supported video formats
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v']

    def __init__(self, config: DisplayConfig):
        self.config = config
        self.logger = logging.getLogger('thermalright.display.frame_manager')

        # Variables for managing backgrounds
        self.current_frame_index = 0
        self.background_frames = []
        self.video_capture = None
        self.image_collection = []
        self.frame_duration = 1.0  # Default duration
        self.frame_start_time = 0
        self.metrics_thread = None
        self.metrics_running = False
        self.metrics_lock = threading.Lock()
        if len(config.metrics_configs) != 0  :
            # Initialize metrics collectors
            self.cpu_metrics = CpuMetrics()
            self.gpu_metrics = GpuMetrics()
            # Variables for real-time metrics
            self.current_metrics = self._get_current_metric()
            # Start metrics update
            self._start_metrics_update()
        else:
            self.cpu_metrics = None
            self.gpu_metrics = None
            self.current_metrics = {}





        # Load background
        self._load_background()

    def _is_video_file(self, file_path: str) -> bool:
        """Check if the file is a supported video format"""
        if not file_path:
            return False

        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in self.SUPPORTED_VIDEO_FORMATS

    def _load_background(self):
        """Load background based on its type and set frame duration"""
        try:
            if self.config.background_type == BackgroundType.IMAGE:
                self._load_static_image()
                self.frame_duration = 1.0  # Fixed 1 second for images
            elif self.config.background_type == BackgroundType.GIF:
                self._load_gif()
            elif self.config.background_type == BackgroundType.VIDEO:
                if HAS_OPENCV and self._is_video_file(self.config.background_path):
                    self._load_video()
                else:
                    if not HAS_OPENCV:
                        self.logger.warning(
                            "OpenCV not available. Video background type is not supported. Falling back to static image.")
                    else:
                        self.logger.warning(
                            f"Unsupported video format. Supported formats: {', '.join(self.SUPPORTED_VIDEO_FORMATS)}. Falling back to static image.")
                    # Fallback to treating video path as a static image
                    self._load_static_image()
                    self.frame_duration = 1.0
            elif self.config.background_type == BackgroundType.IMAGE_COLLECTION:
                self._load_image_collection()
                self.frame_duration = 1.0  # 1 second per image by default

            self.frame_start_time = time.time()
            self.logger.info(
                f"Background loaded: {self.config.background_type}, frame_duration: {self.frame_duration}s")

        except Exception as e:
            self.logger.error(f"Error loading background: {e}")
            raise

    def _load_static_image(self):
        """Load a static image"""
        if not os.path.exists(self.config.background_path):
            raise FileNotFoundError(f"Background image not found: {self.config.background_path}")

        image = Image.open(self.config.background_path)
        image = image.resize((self.config.output_width, self.config.output_height), Image.Resampling.LANCZOS)
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        self.background_frames = [image]

    def _load_gif(self):
        """Load an animated GIF and retrieve duration from metadata"""
        if not os.path.exists(self.config.background_path):
            raise FileNotFoundError(f"Background GIF not found: {self.config.background_path}")

        gif = Image.open(self.config.background_path)
        self.background_frames = []

        # Extract all frames from GIF
        for frame in ImageSequence.Iterator(gif):
            frame_copy = frame.copy()
            frame_copy = frame_copy.resize((self.config.output_width, self.config.output_height),
                                           Image.Resampling.LANCZOS)
            if frame_copy.mode != 'RGBA':
                frame_copy = frame_copy.convert('RGBA')
            self.background_frames.append(frame_copy)

        # Get duration from GIF metadata
        try:
            self.frame_duration = gif.info.get('duration', 100) / 1000.0  # Convert ms to seconds
        except:
            self.frame_duration = 0.1  # Default fallback

        self.logger.debug(f"GIF loaded: {len(self.background_frames)} frames, duration: {self.frame_duration}s")

    def _load_video(self):
        """Load a video and retrieve FPS from metadata"""
        if not os.path.exists(self.config.background_path):
            raise FileNotFoundError(f"Background video not found: {self.config.background_path}")

        if not HAS_OPENCV:
            raise RuntimeError("OpenCV is required for video support but is not available")

        # Verify file format
        if not self._is_video_file(self.config.background_path):
            file_ext = os.path.splitext(self.config.background_path)[1].lower()
            raise RuntimeError(
                f"Unsupported video format '{file_ext}'. Supported formats: {', '.join(self.SUPPORTED_VIDEO_FORMATS)}")

        self.video_capture = cv2.VideoCapture(self.config.background_path)
        if not self.video_capture.isOpened():
            raise RuntimeError(
                f"Cannot open video: {self.config.background_path}. Please check if the file is corrupted or if OpenCV supports this codec.")

        # Get video properties
        fps = self.video_capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        self.frame_duration = 1.0 / fps if fps > 0 else 1.0 / 30  # Fallback 30 FPS

        self.logger.info(f"Video loaded: {os.path.basename(self.config.background_path)}")
        self.logger.info(f"  Format: {os.path.splitext(self.config.background_path)[1].upper()}")
        self.logger.info(f"  FPS: {fps:.2f}")
        self.logger.info(f"  Duration: {duration:.1f}s")
        self.logger.info(f"  Frame duration: {self.frame_duration:.3f}s")

    def _load_image_collection(self):
        """Load an image collection from a folder"""
        if not os.path.isdir(self.config.background_path):
            raise NotADirectoryError(f"Background directory not found: {self.config.background_path}")

        # Search for all images in the folder
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']
        image_files = []

        for ext in image_extensions:
            image_files.extend(glob.glob(os.path.join(self.config.background_path, ext)))
            image_files.extend(glob.glob(os.path.join(self.config.background_path, ext.upper())))

        image_files.sort()  # Alphabetical sort

        if not image_files:
            raise RuntimeError(f"No images found in directory: {self.config.background_path}")

        self.image_collection = image_files
        self.logger.debug(f"Image collection loaded: {len(image_files)} images")

    def _start_metrics_update(self):
        """Start the metrics update thread every second"""
        self.metrics_running = True
        self.metrics_thread = threading.Thread(target=self._metrics_update_loop, daemon=True)
        self.metrics_thread.start()
        self.logger.debug("Metrics update thread started")

    def _metrics_update_loop(self):
        """Metrics update loop every second"""
        while self.metrics_running:
            try:
                with self.metrics_lock:
                    self.current_metrics = self._get_current_metric()

                time.sleep(1.0)  # Update every second

            except Exception as e:
                self.logger.error(f"Error updating metrics: {e}")
                time.sleep(1.0)

    def _get_current_metric(self):
        try:
            # Collect CPU and GPU metrics
            cpu_data = self.cpu_metrics.get_all_metrics()
            gpu_data = self.gpu_metrics.get_all_metrics()
            # Update metrics in a thread-safe manner
            return {
                # CPU metrics
                'cpu_temperature': cpu_data.get('temperature'),
                'cpu_usage': cpu_data.get('usage_percentage'),
                'cpu_frequency': cpu_data.get('frequency'),

                # GPU metrics
                'gpu_temperature': gpu_data.get('temperature'),
                'gpu_usage': gpu_data.get('usage_percentage'),
                'gpu_frequency': gpu_data.get('frequency'),
                'gpu_vendor': gpu_data.get('vendor'),
                'gpu_name': gpu_data.get('name')
            }
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
            raise e

    def get_current_frame(self) -> Image.Image:
        """Get the current background frame"""
        current_time = time.time()

        if self.config.background_type == BackgroundType.IMAGE:
            return self.background_frames[0]

        elif self.config.background_type in [BackgroundType.GIF, BackgroundType.IMAGE_COLLECTION]:
            # Check if we need to change frame
            if current_time - self.frame_start_time >= self.frame_duration:
                self.current_frame_index = (self.current_frame_index + 1) % len(self._get_frame_source())
                self.frame_start_time = current_time

            if self.config.background_type == BackgroundType.GIF:
                return self.background_frames[self.current_frame_index]
            else:  # IMAGE_COLLECTION
                image_path = self.image_collection[self.current_frame_index]
                image = Image.open(image_path)
                image = image.resize((self.config.output_width, self.config.output_height), Image.Resampling.LANCZOS)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                return image

        elif self.config.background_type == BackgroundType.VIDEO:
            if HAS_OPENCV and self.video_capture:
                # Check if we need to read the next frame
                if current_time - self.frame_start_time >= self.frame_duration:
                    self.frame_start_time = current_time

                    # Read next video frame
                    ret, frame = self.video_capture.read()
                    if not ret:
                        # Restart video from beginning
                        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.video_capture.read()

                    if ret:
                        # Convert BGR (OpenCV) to RGB (PIL)
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        image = Image.fromarray(frame_rgb)
                        image = image.resize((self.config.output_width, self.config.output_height),
                                             Image.Resampling.LANCZOS)
                        if image.mode != 'RGBA':
                            image = image.convert('RGBA')

                        # Store current frame
                        self._current_video_frame = image
                        return image
                else:
                    # Return already loaded frame
                    if hasattr(self, '_current_video_frame'):
                        return self._current_video_frame
            else:
                # Fallback to static image behavior if OpenCV not available
                if self.background_frames:
                    return self.background_frames[0]

        # Fallback
        return Image.new('RGBA', (self.config.output_width, self.config.output_height), (0, 0, 0, 255))

    def get_current_frame_info(self) -> Tuple[int, float]:
        """
        Get information about the current frame

        Returns:
            Tuple[int, float]: (frame_index, display_duration)
        """
        return (self.current_frame_index, self.frame_duration)

    def get_current_metrics(self) -> dict:
        """Get current metrics in a thread-safe manner"""
        with self.metrics_lock:
            return self.current_metrics.copy()

    def _get_frame_source(self):
        """Return the appropriate frame source"""
        if self.config.background_type == BackgroundType.GIF:
            return self.background_frames
        elif self.config.background_type == BackgroundType.IMAGE_COLLECTION:
            return self.image_collection
        return []

    def cleanup(self):
        """Clean up resources"""
        self.metrics_running = False
        if self.metrics_thread:
            self.metrics_thread.join(timeout=2.0)

        if self.video_capture:
            self.video_capture.release()

        self.logger.debug("FrameManager cleaned up")

    def __del__(self):
        """Destructor to automatically clean up"""
        self.cleanup()
