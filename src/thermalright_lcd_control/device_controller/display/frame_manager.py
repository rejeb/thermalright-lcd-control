# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import glob
import os

import pyvips

from thermalright_lcd_control.common.logging_config import get_service_logger
from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.common.media_formats import (
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    is_video,
)
from thermalright_lcd_control.device_controller.display.config import BackgroundType, DisplayConfig

# OpenCV is only needed for video backgrounds and costs ~18 MB RSS at import,
# so it is loaded lazily on the first video decode.
import importlib.util

HAS_OPENCV = importlib.util.find_spec("cv2") is not None


class FrameManager:
    """Stateless background-media reader.

    One public method, :meth:`read_frames`, returns every decoded frame with
    its display delay and retains nothing: caching, timing and metrics are the
    caller's (DisplayGenerator's) responsibility."""

    SUPPORTED_VIDEO_FORMATS = VIDEO_EXTENSIONS
    DEFAULT_FRAME_DURATION = 2.0
    MAX_VIDEO_DISPLAY_FPS = 30
    # 900 frames ≈ 30 s at 30 fps ≈ 200 MB at 320x240 RGBA: OOM guard against
    # an arbitrarily long video (hand-edited config path).
    MAX_VIDEO_PRELOAD_FRAMES = 900

    def __init__(self, config: DisplayConfig):
        self.config = config
        self.logger = get_service_logger()

    def read_frames(self) -> list[tuple[pyvips.Image, float]]:
        """Decode the configured background and return [(frame, delay_s), ...]."""
        return list(self.iter_frames())

    def iter_frames(self):
        """Yield (frame, delay_s) one at a time. Videos are decoded lazily so
        the caller can compress each frame before the next is decoded — the
        peak is one raw frame instead of the whole clip."""
        bt = self.config.background_type
        if bt == BackgroundType.GIF:
            yield from self._read_gif()
            return
        if bt == BackgroundType.VIDEO:
            if HAS_OPENCV and is_video(self.config.background_path):
                yield from self._iter_video()
                return
            if not HAS_OPENCV:
                self.logger.warning(
                    "OpenCV not available. Video background type is not supported. "
                    "Falling back to static image.")
            else:
                self.logger.warning(
                    f"Unsupported video format. Supported formats: "
                    f"{', '.join(self.SUPPORTED_VIDEO_FORMATS)}. Falling back to static image.")
            yield from self._read_static()
            return
        if bt == BackgroundType.IMAGE_COLLECTION:
            yield from self._read_collection()
            return
        yield from self._read_static()

    def _read_static(self) -> list[tuple[pyvips.Image, float]]:
        path = self.config.background_path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Background image not found: {path}")
        return [(vu.load_file(path), self.DEFAULT_FRAME_DURATION)]

    def _read_gif(self) -> list[tuple[pyvips.Image, float]]:
        path = self.config.background_path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Background GIF not found: {path}")
        anim = pyvips.Image.new_from_file(path, n=-1, access="random")
        page_h = anim.get("page-height") if anim.get_typeof("page-height") else anim.height
        n_pages = anim.height // page_h
        try:
            delays_ms = anim.get("delay")           # list[int], ms per frame
        except pyvips.Error:
            delays_ms = [100] * n_pages
        frames: list[tuple[pyvips.Image, float]] = []
        for i in range(n_pages):
            page = vu.to_rgba(anim.crop(0, i * page_h, anim.width, page_h))
            d = delays_ms[i] if i < len(delays_ms) else 100
            frames.append((page, (d if d > 0 else 100) / 1000.0))
        return frames

    def _ensure_downloaded(self) -> None:
        """Fetch a missing bundled video on demand, right before decoding it.

        Centralizing the download here means every path that lands a video
        config on the render loop — a rotation orientation swap, an engine
        reload, a freshly seeded config — self-heals a missing ``.mp4`` without
        each caller having to remember to pre-download. Best-effort: failures
        are logged and swallowed by ``ensure_background_downloaded`` (the
        existence check below then raises with a clear message)."""
        from thermalright_lcd_control.device_controller.display.asset_download import (
            DEFAULT_MEDIA_ENDPOINT,
            ensure_background_downloaded,
        )
        endpoint = getattr(self.config, "media_endpoint", None) or DEFAULT_MEDIA_ENDPOINT
        ensure_background_downloaded(self.config.background_path, endpoint)

    def _iter_video(self):
        import cv2
        self._ensure_downloaded()
        path = self.config.background_path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Background video not found: {path}")

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(
                f"Cannot open video: {path}. "
                "Please check if the file is corrupted or if OpenCV supports this codec.")

        count = 0
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            display_fps = min(fps if fps > 0 else 30, self.MAX_VIDEO_DISPLAY_FPS)
            delay = 1.0 / display_fps
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                # Media is already materialized at the device resolution;
                # image_encoder._fit stays as the safety net.
                yield (vu.to_rgba(vu.from_numpy(
                    cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))), delay)
                count += 1
                if count >= self.MAX_VIDEO_PRELOAD_FRAMES:
                    self.logger.warning(
                        f"Video truncated to {self.MAX_VIDEO_PRELOAD_FRAMES} frames "
                        f"({self.MAX_VIDEO_PRELOAD_FRAMES / display_fps:.0f}s at "
                        f"{display_fps:.0f}fps): {path}")
                    break
        finally:
            cap.release()

        if not count:
            raise RuntimeError(f"No frames could be read from video: {path}")
        self.logger.info(
            f"Video decoded: {os.path.basename(path)} — {count} frames, "
            f"display FPS {display_fps:.0f}, frame duration {delay:.3f}s")

    def _read_collection(self) -> list[tuple[pyvips.Image, float]]:
        return [(vu.load_file(p), self.DEFAULT_FRAME_DURATION)
                for p in self._list_collection_files()]

    def _list_collection_files(self) -> list[str]:
        """Sorted image files of the collection folder (raises when empty/missing)."""
        if not os.path.isdir(self.config.background_path):
            raise NotADirectoryError(
                f"Background directory not found: {self.config.background_path}")

        image_files = []
        for ext in IMAGE_EXTENSIONS:
            image_files.extend(glob.glob(os.path.join(self.config.background_path, f"*{ext}")))
            image_files.extend(
                glob.glob(os.path.join(self.config.background_path, f"*{ext.upper()}")))
        image_files.sort()

        if not image_files:
            raise RuntimeError(f"No images found in directory: {self.config.background_path}")
        return image_files

