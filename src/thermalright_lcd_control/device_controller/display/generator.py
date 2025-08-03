# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import os
from typing import Dict, Any, Tuple

from PIL import Image, ImageDraw

from .config import DisplayConfig
from .frame_manager import FrameManager
from .text_renderer import TextRenderer
from .utils import async_background
from ...common.logging_config import LoggerConfig


class DisplayGenerator:
    """Display image generator with dynamic background and real-time metrics"""

    def __init__(self, config: DisplayConfig):
        self.config = config
        self.logger = self.logger = LoggerConfig.setup_service_logger()

        # Initialize components
        self.frame_manager = FrameManager(config)
        self.text_renderer = TextRenderer(config)  # Pass config for global font

        self.logger.info(f"DisplayGenerator initialized with background type: {self.config.background_type}")
        self.logger.info(f"Global font: {self.config.global_font_path or 'Default system font'}")

    def _add_foreground_image(self, background: Image.Image) -> Image.Image:
        """Add foreground image to background"""
        if not self.config.foreground_image_path or not os.path.exists(self.config.foreground_image_path):
            return background

        try:
            foreground = Image.open(self.config.foreground_image_path)
            if foreground.mode != 'RGBA':
                foreground = foreground.convert('RGBA')

            # Apply transparency
            if self.config.foreground_alpha < 1.0:
                alpha = foreground.split()[-1]  # Alpha channel
                alpha = alpha.point(lambda p: int(p * self.config.foreground_alpha))
                foreground.putalpha(alpha)

            # Compose foreground image
            result = background.copy()
            result.paste(foreground, self.config.foreground_position, foreground)
            return result

        except Exception as e:
            self.logger.warning(f"Cannot load foreground image: {e}")
            return background

    def generate_frame_with_metrics(self,metrics:dict) -> Image.Image:
        """
        Generate a complete frame with all elements and real-time metrics
        """
        # Get current background
        background = self.frame_manager.get_current_frame()

        # Add foreground image if configured
        result = self._add_foreground_image(background)

        # Create drawing object
        draw = ImageDraw.Draw(result)



        # Draw metrics
        self.text_renderer.render_metrics(draw, metrics, self.config.metrics_configs)

        # Draw date (dd/mm format)
        self.text_renderer.render_date(draw, self.config.date_config)

        # Draw time (HH:MM format)
        self.text_renderer.render_time(draw, self.config.time_config)

        return result.convert('RGB')

    def generate_frame(self) -> Image.Image:
        # Get current real-time metrics
        metrics = self.frame_manager.get_current_metrics()

        return self.generate_frame_with_metrics(metrics)

    def get_frame_with_duration(self) -> Tuple[Image, float]:
        """
        Generate a complete frame and return it with its display duration
        
        Returns:
            Tuple[Image.Image, float]: (generated_image, display_duration_seconds)
        """
        # Generate the complete frame
        frame = self.generate_frame()

        # Get the display duration from frame manager
        _, duration = self.frame_manager.get_current_frame_info()

        return frame, duration

    def get_current_frame_info(self) -> Tuple[int, float]:
        """
        Get information about the current background frame
        
        Returns:
            Tuple[int, float]: (frame_index, display_duration)
        """
        return self.frame_manager.get_current_frame_info()

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.frame_manager.get_current_metrics()

    def save_frame(self, output_path: str):
        """Generate and save a frame"""
        frame = self.generate_frame()
        frame.save(output_path)
        self.logger.debug(f"Frame saved to: {output_path}")

    def save_frame_with_duration(self, output_path: str) -> float:
        """
        Generate and save a frame, returning its display duration
        
        Returns:
            float: Display duration in seconds
        """
        frame, duration = self.get_frame_with_duration()
        frame.save(output_path)
        self.logger.debug(f"Frame saved to: {output_path} (duration: {duration}s)")
        return duration

    @async_background
    def cleanup(self):
        """Clean up resources"""
        self.frame_manager.cleanup()
        self.logger.debug("DisplayGenerator cleaned up")

    def __del__(self):
        """Destructor to automatically clean up"""
        self.cleanup()
