# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import glob
import os
import threading
import time
import traceback
from threading import Timer
from typing import Tuple
from PIL import Image, ImageSequence

from .config import BackgroundType, DisplayConfig
from ..metrics.cpu_metrics import CpuMetrics
from ..metrics.gpu_metrics import GpuMetrics
from ...common.logging_config import get_service_logger

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
    DEFAULT_FRAME_DURATION = 2.0
    def __init__(self, config: DisplayConfig):
        self.config = config
    def __init__(self, config: DisplayConfig):
        stack = ''.join(traceback.format_stack())
        print(f"Stack trace:\n{stack}")
        self.config = config
        self.logger = get_service_logger()

        # Variables for managing backgrounds
        self.current_frame_index = 0
        self.background_frames = []
        self.gif_durations = []
        self.frame_duration = self.DEFAULT_FRAME_DURATION
        self.frame_start_time = 0
        self.metrics_thread: Timer | None = None
        self.metrics_running = False
        if len(config.metrics_configs) != 0:
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
            self._stop_metrics_update()

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
            elif self.config.background_type == BackgroundType.IMAGE_COLLECTION:
                self._load_image_collection()

            self.frame_start_time = time.time()
            self.logger.info(
                f"Background loaded: {self.config.background_type}, frame_duration: {self.frame_duration}s")

        except Exception as e:
            self.logger.error(f"Error loading background: {e}")
            raise

    def _load_static_image(self) -> None:
        """Load a static image"""
        if not os.path.exists(self.config.background_path):
            raise FileNotFoundError(f"Background image not found: {self.config.background_path}")

        image = Image.open(self.config.background_path)
        image = self._resize_image(image)
        self.background_frames = [image]

    def _resize_image(self, image: Image.Image) -> Image.Image:
        image = image.resize((self.config.output_width, self.config.output_height), Image.Resampling.LANCZOS)
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        return image

    def _load_gif(self):
        """Load an animated GIF and retrieve duration from metadata"""
        if not os.path.exists(self.config.background_path):
            raise FileNotFoundError(f"Background GIF not found: {self.config.background_path}")

        gif = Image.open(self.config.background_path)

        self.background_frames = []

        # Extract all frames from GIF
        for frame in ImageSequence.Iterator(gif):
            gif_frame_duration = self._gif_duration(frame)
            self.logger.info(f"Extracting GIF duration from metadata... {gif_frame_duration}")
            frame_copy = frame.copy()
            frame_copy = self._resize_image(frame_copy)
            self.background_frames.append(frame_copy)
            self.gif_durations.append(gif_frame_duration)

        self.frame_duration = self.gif_durations[0]

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

        video_capture = cv2.VideoCapture(self.config.background_path)
        if not video_capture.isOpened():
            raise RuntimeError(
                f"Cannot open video: {self.config.background_path}. Please check if the file is corrupted or if OpenCV supports this codec.")

        # Get video properties
        fps = video_capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        self.frame_duration = 1.0 / fps if fps > 0 else 1.0 / 30  # Fallback 30 FPS

        for i in range(frame_count):
            ret, frame = video_capture.read()
            if not ret:
                break
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = self._resize_image(Image.fromarray(frame_rgb))
            self.background_frames.append(image)

        video_capture.release()

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

        for image_path in image_files:
            image = Image.open(image_path)
            image = self._resize_image(image)
            self.background_frames.append(image)

        self.logger.debug(f"Image collection loaded: {len(image_files)} images")

    def _start_metrics_update(self):
        """Start the metrics update thread every second"""
        print("Starting metrics update thread ...")
        self.metrics_running = True
        self.metrics_thread = threading.Timer(interval=2.0,function=self._metrics_update_loop)
        self.metrics_thread.start()
        self.logger.debug("Metrics update thread started")

    def _stop_metrics_update(self):
        """Start the metrics update thread every second"""
        self.metrics_running = False
        self.metrics_thread.cancel()
        self.metrics_thread = None
        self.logger.debug("Metrics update thread started")

    def _metrics_update_loop(self):
        print("getting new metrics")
        start = time.time()
        new_metrics = self._get_current_metric()
        print(f"getting new metrics duration: {time.time() - start}")
        self.current_metrics = new_metrics
        if self.metrics_running:
            self.metrics_thread = threading.Timer(interval=2.0, function=self._metrics_update_loop)
            self.metrics_thread.start()

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

    def _gif_duration(self, frame: Image.Image) -> float:
        # Get duration from GIF metadata
        try:
            return frame.info.get('duration', 100) / 1000.0  # Convert ms to seconds
        except:
            return 0.1  # Default fallback

    def get_current_frame(self) -> Image.Image:
        """Get the current background frame"""
        current_time = time.time()

        if current_time - self.frame_start_time >= self.frame_duration:
            self.frame_start_time = current_time
            self.current_frame_index = (self.current_frame_index + 1) % len(self.background_frames)

        if self.config.background_type == BackgroundType.GIF:
            self.frame_duration = self.gif_durations[self.current_frame_index]

        return self.background_frames[self.current_frame_index]

    def get_current_frame_info(self) -> Tuple[int, float]:
        """
        Get information about the current frame

        Returns:
            Tuple[int, float]: (frame_index, display_duration)
        """
        display_duration = self.wait_duration if self.wait_duration else self.frame_duration
        return self.current_frame_index, display_duration

    def get_current_metrics(self) -> dict:
        """Get current metrics in a thread-safe manner"""
        return self.current_metrics

    def cleanup(self):
        """Clean up resources"""
        self.metrics_running = False
        if self.metrics_thread:
            self.metrics_thread.cancel()
            self.metrics_thread = None

        self.logger.debug("FrameManager cleaned up")

    def __del__(self):
        """Destructor to automatically clean up"""
        self.cleanup()
