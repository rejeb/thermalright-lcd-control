# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import os
import time
from datetime import datetime
from typing import Any

import pyvips

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import DisplayConfig
from thermalright_lcd_control.device_controller.display.frame_manager import FrameManager
from thermalright_lcd_control.device_controller.display.text_renderer import TextRenderer
from thermalright_lcd_control.device_controller.display.utils import trim_native_heap
from thermalright_lcd_control.device_controller.metrics import shared_collector

# Singleton registry: one generator per configured device, shared between the
# device render loop and the GUI preview. Mutations happen on the render
# thread; get() from the GUI thread is a plain dict read.
_instances: dict[str, "DisplayGenerator"] = {}


class DisplayGenerator:
    """Per-device generator holding the composed (bg+fg, rotated) frame cache,
    frame timing, and the lazily-rebuilt text overlay. Metrics refresh cadence
    is owned by MetricsCollector.values(); this class only detects changes."""

    #: JPEG quality of the cached base frames. The cache holds compressed bytes
    #: instead of raw bitmaps: a 1920x440 video clip is ~19 MB instead of ~365 MB.
    BASE_JPEG_QUALITY = 85

    def __init__(self, config: DisplayConfig):
        self.config = config
        self.logger = LoggerConfig.setup_service_logger()
        self.text_renderer = TextRenderer()
        self._metrics = shared_collector() if config.metrics_configs else None
        self._metrics_snapshot: dict = {}   # identity-stable empty fallback
        self._foreground: pyvips.Image | None = self._load_foreground()
        # Composed base frames: [(JPEG bytes of bg+fg, delay_s), ...], unrotated.
        # Compressed to keep RAM proportional to the encoded size, not the raw
        # bitmaps; the device path decodes one frame at a time on a cache miss.
        self._frames: list[tuple[bytes, float]] = self._build_frames()
        # Timing metadata that must survive drop_media()
        self._frame_count_meta = len(self._frames)
        self._frame_duration_meta = self._frames[0][1]
        # Frame timing (moved from FrameManager)
        self.current_frame_index = 0
        self.frame_start_time = time.time()
        # Overlay
        _metrics = self.get_current_metrics()
        self._overlay: pyvips.Image | None = self._build_overlay(_metrics, datetime.now())
        self._overlay_metrics: dict = _metrics
        self._overlay_time_key: int = self._time_key()
        self._overlay_version: int = 0  # incremented each time the overlay is rebuilt

        self.logger.info(f"DisplayGenerator initialized with background type: {self.config.background_type}")
        self.logger.info(f"Global font: {self.config.global_font_path or 'Default system font'}")

    # ── singleton registry (one generator per configured device) ────────────

    @classmethod
    def acquire(cls, device_id: str, config: DisplayConfig) -> "DisplayGenerator":
        """Existing instance for ``device_id`` or a freshly registered one."""
        gen = _instances.get(device_id)
        if gen is None:
            gen = cls(config)
            _instances[device_id] = gen
        return gen

    @classmethod
    def replace(cls, device_id: str, config: DisplayConfig) -> "DisplayGenerator":
        """Release any existing instance and register a fresh one (config change)."""
        cls.release_device(device_id)
        return cls.acquire(device_id, config)

    @classmethod
    def get(cls, device_id: str) -> "DisplayGenerator | None":
        """Peek without creating (preview path)."""
        return _instances.get(device_id)

    @classmethod
    def release_device(cls, device_id: str) -> None:
        """Destroy the instance for ``device_id`` and free its RAM immediately."""
        gen = _instances.pop(device_id, None)
        if gen is not None:
            gen.release()
            trim_native_heap()

    # ── frame building ───────────────────────────────────────────────────────

    def _load_foreground(self) -> pyvips.Image | None:
        """Load and prepare the foreground image once at startup."""
        path = self.config.foreground_image_path
        if not path or not os.path.exists(path):
            return None
        try:
            fg = vu.load_file(path)
            if self.config.foreground_alpha < 1.0:
                alpha = fg[3] * self.config.foreground_alpha
                fg = fg[0:3].bandjoin(alpha.cast("uchar"))
            self.logger.info(f"Foreground image loaded: {path}")
            return fg
        except Exception as e:
            self.logger.warning(f"Cannot load foreground image: {e}")
            return None

    def _build_frames(self) -> list[tuple[bytes, float]]:
        """Read the media, paste the foreground, and store each frame as JPEG
        bytes. The cached frames stay UNROTATED (preview space); rotation is
        applied only on the device path, in compose_device_frame."""
        fg = self._foreground
        out: list[tuple[bytes, float]] = []
        fx, fy = self.config.foreground_position
        for frame, delay in FrameManager(self.config).iter_frames():
            if fg is not None:
                frame = vu.overlay_at(frame, fg, fx, fy)
            out.append((self._encode_base(frame), delay))
        return out

    def _encode_base(self, frame: pyvips.Image) -> bytes:
        return vu.jpeg_bytes(frame, quality=self.BASE_JPEG_QUALITY)

    @staticmethod
    def _decode_base(data: bytes) -> pyvips.Image:
        """Decoded RGB image of a cached frame."""
        return vu.from_jpeg(data)

    def _apply_rotation(self, img: pyvips.Image) -> pyvips.Image:
        return vu.rotate(img, self.config.rotation)

    def _overlay_size(self) -> tuple[int, int]:
        """Overlay layer size = unrotated canvas (same space as the base frames)."""
        return self.config.output_width, self.config.output_height

    # ── frame timing (moved from FrameManager) ───────────────────────────────

    @property
    def frame_count(self) -> int:
        return len(self._frames) if self._frames else self._frame_count_meta

    @property
    def frame_duration(self) -> float:
        if self._frames:
            return self._frames[self.current_frame_index][1]
        return self._frame_duration_meta

    def peek_next_frame_idx(self) -> int:
        """Frame index that will be active after the next advance_frame_time()."""
        if time.time() - self.frame_start_time >= self.frame_duration:
            return (self.current_frame_index + 1) % self.frame_count
        return self.current_frame_index

    def advance_frame_time(self) -> None:
        """Advance frame timing state without rendering."""
        if time.time() - self.frame_start_time >= self.frame_duration:
            self.frame_start_time += self.frame_duration
            self.current_frame_index = (self.current_frame_index + 1) % self.frame_count

    # ── low-memory mode (window minimized / inactive device) ────────────────

    @property
    def media_resident(self) -> bool:
        return bool(self._frames)

    def ensure_media(self) -> bool:
        """Re-read the clip and re-composite the foreground after drop_media().
        Returns True when a reload actually happened. Render thread only."""
        print(f"ensure_media frames {len(self._frames)}")
        if self._frames:
            return False
        self._frames = self._build_frames()
        self._frame_count_meta = len(self._frames)
        self._frame_duration_meta = self._frames[0][1]
        self.current_frame_index %= max(1, len(self._frames))
        return True

    # ── public frame APIs ────────────────────────────────────────────────────

    def get_base_frame(self) -> bytes | None:
        """Preview/base path: current cached bg+fg frame as JPEG bytes (read-only
        for callers). Advances timing exactly once per call. None while the
        media is dropped."""
        if not self._frames:
            return None
        idx = self.peek_next_frame_idx()
        self.advance_frame_time()
        return self._frames[idx][0]

    def current_base_frame(self) -> bytes | None:
        """Current frame (JPEG bytes) WITHOUT advancing timing (GUI preview
        reads this and can hand it straight to QPixmap.loadFromData; the render
        loop owns timing)."""
        if not self._frames:
            return None
        return self._frames[self.current_frame_index][0]

    def get_frame_with_metrics(self) -> pyvips.Image:
        """Device path: decode the current base frame, paste the text overlay,
        apply rotation."""
        base = self.get_base_frame()
        return self.compose_device_frame(base)

    def get_frame_with_duration(self) -> tuple[pyvips.Image, float]:
        return self.get_frame_with_metrics(), self.frame_duration

    # ── overlay ──────────────────────────────────────────────────────────────

    def _build_overlay(self, metrics: dict, now: datetime) -> pyvips.Image:
        """Render all text elements onto a transparent RGBA layer."""
        overlay = vu.solid(*self._overlay_size(), (0, 0, 0, 0))
        overlay = self.text_renderer.render_metrics(overlay, metrics, self.config.metrics_configs)
        overlay = self.text_renderer.render_texts(overlay, getattr(self.config, "texts", None))
        overlay = self.text_renderer.render_date(overlay, self.config.date_config, now)
        overlay = self.text_renderer.render_time(overlay, self.config.time_config, now)
        overlay = self.text_renderer.render_weekday(
            overlay, getattr(self.config, "weekday_config", None), now)
        return overlay

    def _time_key(self) -> int:
        """Staleness key for the overlay's time-dependent refresh.

        Granularity follows what is configured: minute when a time widget or
        metrics are present (unchanged historical cadence), day when only a
        date widget is enabled (refresh at midnight), constant otherwise so a
        widget-less overlay is never rebuilt until the config changes."""
        now = datetime.now()
        tc, dc = self.config.time_config, self.config.date_config
        if (tc is not None and tc.enabled) or self.config.metrics_configs:
            return now.hour * 60 + now.minute
        if dc is not None and dc.enabled:
            return now.toordinal()
        return -1

    def sync_overlay(self) -> int:
        """Rebuild the text overlay if the metrics or the time key changed,
        bumping ``_overlay_version``. Cheap on the common path (identity/int
        compare)."""
        metrics = self.get_current_metrics()
        time_key = self._time_key()
        if metrics is not self._overlay_metrics or time_key != self._overlay_time_key:
            self._overlay = self._build_overlay(metrics, datetime.now())
            self._overlay_metrics = metrics
            self._overlay_time_key = time_key
            self._overlay_version += 1
        return self._overlay_version

    def compose_device_frame(self, base: bytes) -> pyvips.Image:
        """Device path only: decode the cached JPEG ``base``, composite the
        lazily-rebuilt text overlay, and apply rotation. The cached base frames
        (and the preview) stay unrotated. Does NOT advance frame timing
        (``get_base_frame`` already did)."""
        self.sync_overlay()

        result = self._decode_base(base)
        if self._overlay is not None:
            result = vu.overlay_at(result, self._overlay, 0, 0)

        return self._apply_rotation(vu.to_rgb(result))

    def refresh_overlay(self, config) -> None:
        """Apply an overlay-only config change (metrics/date/time/text/font) in
        place, reusing the cached frames. Cheap (~ms) compared to rebuilding the
        generator (which re-decodes the video). ``_overlay_version`` is bumped so
        the device encode cache invalidates (a rotation change is covered: the
        cached frames are unrotated, rotation is applied at compose time)."""
        self.config = config
        self.text_renderer = TextRenderer()
        self._metrics = shared_collector() if config.metrics_configs else None
        self._overlay = self._build_overlay(self.get_current_metrics(), datetime.now())
        self._overlay_metrics = self.get_current_metrics()
        self._overlay_time_key = self._time_key()
        self._overlay_version += 1

    # ── metrics (refresh cadence owned by MetricsCollector) ─────────────────

    def get_current_metrics(self) -> dict[str, Any]:
        """Current metric values; the same dict object is returned until the
        collector refreshes (sync_overlay uses identity to detect a change)."""
        if self._metrics is None:
            return self._metrics_snapshot  # identity-stable
        return self._metrics.values()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.debug("DisplayGenerator cleaned up")

    def release(self) -> None:
        """cleanup() + drop the cached frames, overlay and foreground.

        Call when the generator is discarded (config change / device removal),
        render thread only: the retained clip can be hundreds of MB and must be
        freed even if something still holds a reference to this object."""
        self.cleanup()
        self._frames = []
        self._overlay = None
        self._foreground = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()
        return False

    def __del__(self):
        # Best-effort safety net only; explicit cleanup() is the contract.
        try:
            self.cleanup()
        except Exception:
            pass

    @property
    def frames(self):
        return self._frames
