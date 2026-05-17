# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Single source of truth for supported media file extensions."""
from __future__ import annotations

import os

IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp",
)
VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v",
)


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def is_video(path: str) -> bool:
    return _ext(path) in VIDEO_EXTENSIONS
