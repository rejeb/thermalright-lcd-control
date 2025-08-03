# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Configuration loading utilities
"""

from pathlib import Path

import yaml

from ...common.logging_config import get_gui_logger


def get_default_config():
    """Get default configuration"""
    return {
        'paths': {
            'backgrounds_dir': './themes/backgrounds',
            'foregrounds_dir': './themes/foregrounds'
        },
        'window': {
            'default_width': 1000,
            'default_height': 600,
            'min_width': 800,
            'min_height': 600
        },
        'supported_formats': {
            'images': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'],
            'videos': ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v'],
            'gifs': ['.gif']
        }
    }


def load_config(config_file_path=None):
    """Load configuration from YAML file"""
    logger = get_gui_logger()
    default_config = get_default_config()

    if not config_file_path:
        logger.warning("No config file specified, using default configuration")
        return default_config

    try:
        config_path = Path(config_file_path)
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_file_path}, using default configuration")
            return default_config

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Merge with default config to ensure all keys exist
        merged_config = default_config.copy()
        if config:
            # Deep merge
            for key, value in config.items():
                if isinstance(value, dict) and key in merged_config:
                    merged_config[key].update(value)
                else:
                    merged_config[key] = value

        return merged_config

    except Exception as e:
        logger.error(f"Error loading config file {config_file_path}: {e}")
        logger.warning("Using default configuration")
        return default_config