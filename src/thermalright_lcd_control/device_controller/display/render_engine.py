# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Controller-owned render loop.

One :class:`RenderEngine` per configured device drives the per-device
:class:`DisplayGenerator` singleton (``DisplayGenerator.acquire``). Each tick
it advances the cached **base frame** (background + foreground, pre-rotated) —
the GUI preview reads the same singleton via ``current_base_frame()`` — and,
when a device sink is attached, calls ``sink.send(frame_idx)`` to push the
already-encoded frame from the sink's cache.

When metrics change, the engine fires a one-shot background thread that
generates **all frames** at once (compose + encode), storing them in the
sink's :class:`FrameEncodeCache`. The per-frame compose+encode work is
parallelised with a :class:`~concurrent.futures.ThreadPoolExecutor` so that
large clips (e.g. 150 frames on a 1920×440 screen) finish in well under 500 ms
instead of ~5 s sequentially.  pyvips operations release the GIL so real
parallelism is achieved even in CPython.

Config changes arrive on the shared :class:`EventBus`; the engine rebuilds its
generator on its own loop thread (cheap flag set on the publisher thread).
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.device_controller.display.asset_download import (
    DEFAULT_MEDIA_ENDPOINT,
)
from thermalright_lcd_control.device_controller.display.config_loader import ConfigLoader
from thermalright_lcd_control.device_controller.display.event_bus import Topic
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator

# Number of worker threads for the parallel encode pass.
# pyvips releases the GIL so threads run truly in parallel.
# 4 workers is a safe default: diminishing returns beyond ~CPU count,
# and we don't want to saturate a low-core embedded/SBC system.
_ENCODE_WORKERS = os.cpu_count() / 2 or 4


class RenderEngine:
    def __init__(self, width: int, height: int, config_file: str,
                 device_id: str, sink=None, media_active: bool = True,
                 media_endpoint: str = DEFAULT_MEDIA_ENDPOINT):
        self.width = width
        self.height = height
        self.config_file = config_file
        self.media_endpoint = media_endpoint or DEFAULT_MEDIA_ENDPOINT
        self.logger = LoggerConfig.setup_service_logger()
        self._sink = sink
        self._reload_id = str(device_id)
        self._event_bus = None

        self._stop_event = threading.Event()
        self._reload_requested = threading.Event()
        self._pending_config = None
        self._media_active = bool(media_active)

        # Tracks the overlay version for which we last launched a full encode
        # pass, so we fire the background thread exactly once per metrics change.
        self._last_encoded_overlay_version: int = -1
        # Guards concurrent encode passes: only one runs at a time.
        # Non-blocking acquire — if one is already running the new trigger is
        # dropped; the next tick will re-detect the stale version and retry.
        self._encode_lock = threading.Lock()

        self._generator = DisplayGenerator.acquire(self._reload_id,
                                                   self._build_config(None))
        self._push_frame_count()

    # --- generator / reload ---

    def _build_config(self, config: dict | None):
        """Build a DisplayConfig from an in-memory dict (live edit) or the file."""
        loader = ConfigLoader()
        if config is not None:
            return loader.load_config_from_dict(config, self.width, self.height,
                                                media_endpoint=self.media_endpoint)
        return loader.load_config(self.config_file, self.width, self.height,
                                  media_endpoint=self.media_endpoint)

    @staticmethod
    def _media_unchanged(old, new) -> bool:
        return (old.background_path == new.background_path
                and old.background_type == new.background_type
                and old.foreground_image_path == new.foreground_image_path
                and tuple(old.foreground_position) == tuple(new.foreground_position)
                and old.foreground_alpha == new.foreground_alpha)

    def _push_frame_count(self) -> None:
        if self._sink is not None:
            setter = getattr(self._sink, "set_frame_count", None)
            if callable(setter):
                setter(self._generator.frame_count)

    def set_media_active(self, active: bool) -> None:
        """Called from the GUI thread when the window is hidden/shown."""
        if not active:
            self._media_active = bool(active)

    def _get_generator(self) -> DisplayGenerator:
        if self._reload_requested.is_set():
            self._reload_requested.clear()
            new_cfg = self._build_config(self._pending_config)
            self._pending_config = None
            cur = self._generator
            if cur is not None and self._media_unchanged(cur.config, new_cfg):
                self.logger.info(f"Overlay-only refresh: {self.config_file}")
                cur.refresh_overlay(new_cfg)
            else:
                self.logger.info(f"Full config rebuild: {self.config_file}")
                self._generator = DisplayGenerator.replace(self._reload_id, new_cfg)
                if self._sink is not None:
                    invalidate = getattr(self._sink, "invalidate_cache", None)
                    if callable(invalidate):
                        invalidate()
            # Force a fresh encode pass for the new generator state.
            self._last_encoded_overlay_version = -1
            self._push_frame_count()
        return self._generator

    def attach_event_bus(self, event_bus, device_id: str) -> None:
        self._reload_id = str(device_id)
        self._event_bus = event_bus
        event_bus.subscribe(Topic.CONFIG_RELOAD, self._on_config_reload)

    def _on_config_reload(self, device_id, config=None) -> None:
        if str(device_id) == self._reload_id:
            self._pending_config = config
            self._reload_requested.set()

    # --- background encode pass ---

    @staticmethod
    def _encode_one_frame(
            frame_idx: int,
            base_bytes: bytes,
            gen: DisplayGenerator,
            encode_fn,
    ) -> int:
        """Compose + encode a single frame. Designed to run inside a thread pool.

        ``base_bytes`` is read-only JPEG bytes from the generator's frame list.
        ``gen.compose_device_frame`` is thread-safe when the overlay is not
        being rebuilt concurrently: we snapshot the overlay version before
        submitting the pool (via ``sync_overlay`` in the caller) so all workers
        operate on the same frozen overlay.  pyvips calls release the GIL, so
        workers run in true parallel on multi-core machines."""
        composed = gen.compose_device_frame(base_bytes)
        encode_fn(frame_idx, composed)
        return frame_idx

    def _encode_all_frames(self, gen: DisplayGenerator, overlay_version: int) -> None:
        """Compose + encode every frame for the current overlay in parallel and
        store the results in the sink's cache. Runs on a dedicated daemon thread
        (the outer thread) so the render loop is never blocked. Within this
        method a :class:`ThreadPoolExecutor` parallelises the per-frame work.

        Only one pass runs at a time (_encode_lock). If a newer version arrives
        while this pass is running, it will be picked up on the next tick."""
        if not self._encode_lock.acquire(blocking=False):
            return
        try:

            sink = self._sink
            if sink is None:
                return
            encode_fn = getattr(sink, "encode_and_cache_frame", None)
            if not callable(encode_fn):
                return

            if not gen.media_resident:
                gen.ensure_media()

            # Snapshot the overlay once so every worker thread sees the same
            # frozen overlay — avoids a race with sync_overlay() increments.
            gen.sync_overlay()

            frame_count = gen.frame_count
            # Build the list of (frame_idx, base_bytes) up front so workers
            # only read immutable bytes; no shared mutable state in the pool.
            frames = [(i, gen.frames[i][0]) for i in range(frame_count)]

            n_workers = min(_ENCODE_WORKERS, frame_count)
            with ThreadPoolExecutor(max_workers=n_workers,
                                    thread_name_prefix=f"enc-{self._reload_id}") as pool:
                futures = {
                    pool.submit(self._encode_one_frame, idx, base, gen, encode_fn): idx
                    for idx, base in frames
                    if not self._stop_event.is_set()
                }
                for future in as_completed(futures):
                    if self._stop_event.is_set():
                        # Cancel remaining work — pool.__exit__ will wait for
                        # already-running futures but not start new ones.
                        pool.shutdown(wait=False, cancel_futures=True)
                        break
                    try:
                        future.result()
                    except Exception as e:
                        self.logger.error(
                            f"Frame encode error (idx={futures[future]}): {e}",
                            exc_info=True,
                        )

        except Exception as e:
            self.logger.error(f"Background encode error: {e}", exc_info=True)
        finally:
            self._encode_lock.release()

    def _trigger_encode_if_needed(self, gen: DisplayGenerator, overlay_version: int) -> None:
        """Spawn a background encode pass when the overlay version changed.
        Non-blocking: returns immediately after thread creation."""
        if overlay_version == self._last_encoded_overlay_version:
            return
        self._last_encoded_overlay_version = overlay_version
        t = threading.Thread(
            target=self._encode_all_frames,
            args=(gen, overlay_version),
            daemon=True,
            name=f"encode-{self._reload_id}-v{overlay_version}",
        )
        t.start()

    # --- loop ---

    def _tick(self) -> float:
        gen = self._get_generator()
        if not gen.media_resident:
            gen.ensure_media()

        # Advance base-frame timing (GUI preview + current_frame_index).
        gen.get_base_frame()

        if self._sink is not None:
            frame_idx = gen.current_frame_index
            version = gen.sync_overlay()
            self._trigger_encode_if_needed(gen, version)
            self._sink.send(frame_idx)

        return gen.frame_duration

    def run(self) -> None:
        self.logger.info(f"RenderEngine running for {self._reload_id} "
                         f"({self.width}x{self.height}), sink={'yes' if self._sink else 'no'}")
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                delay = self._tick()
            except Exception as e:
                self.logger.error(f"Render error: {e}", exc_info=True)
                delay = 1.0
            self._stop_event.wait(delay)

    def stop(self) -> None:
        """Signal the loop to exit and detach from the bus.

        Does NOT close the sink: the render thread may be inside a ``send`` on
        the device transport, and closing a hidapi/pyusb handle under a live
        write can crash in the native lib. ``close()`` must be called after the
        loop thread has been joined."""
        self._stop_event.set()
        if self._event_bus is not None:
            self._event_bus.unsubscribe(Topic.CONFIG_RELOAD, self._on_config_reload)

    def close(self) -> None:
        """Release the generator (via the registry, freeing its frames) and the
        device transport. Call after join."""
        device_id = getattr(self, "_reload_id", None)
        if device_id is not None:
            DisplayGenerator.release_device(device_id)
        self._generator = None
        if self._sink is not None:
            close = getattr(self._sink, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as e:
                    self.logger.debug(f"Error closing sink: {e}")
