# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Metrics class hierarchy and single entry point.

A :class:`Metrics` subclass covers one device domain (CPU, GPU, memory, disk,
network, system). Each ``metric_<key>`` method returns the value of one widget
key; :meth:`Metrics.collect` discovers and evaluates them all, so adding a
metric is just adding a method — error handling and logging live here once.

:class:`MetricsCollector` aggregates every domain and is the only type the
consumers (FrameManager, AppBackend) see. :meth:`MetricsCollector.values`
returns internally-refreshed values: it re-collects inline when the cached
values are older than ``max_age`` and returns the *same dict object*
otherwise — the overlay renderer relies on dict identity to detect a refresh.
No lock: value consistency across a refresh is not required, and a benign
concurrent double-collect is cheaper than contention on the render path.
"""
from __future__ import annotations

import time
from threading import Timer
from thermalright_lcd_control.common.logging_config import LoggerConfig

_METRIC_PREFIX = "metric_"
_MIB = 1024 ** 2


def read_sysfs_float(path: str, scale: float = 1.0) -> float | None:
    """Read a float from a sysfs-style file; None when absent/unreadable."""
    try:
        with open(path) as f:
            return float(f.read().strip()) * scale
    except Exception:
        return None


class CounterRates:
    """Throughputs (MiB/s) derived from cumulative byte counters.

    Two consecutive snapshots at least ``min_interval`` seconds apart (below
    that the previous rates are kept — a shorter window mostly measures
    noise). The first update returns 0.0; a counter reset never yields a
    negative rate."""

    def __init__(self, n: int = 2, min_interval: float = 0.5):
        self._min_interval = min_interval
        self._last: tuple[float, tuple[int, ...]] | None = None
        self.rates: tuple[float, ...] = (0.0,) * n

    def update(self, counters: tuple[int, ...]) -> tuple[float, ...]:
        now = time.monotonic()
        if self._last is None:
            self._last = (now, counters)
            return self.rates
        last_t, last_counters = self._last
        elapsed = now - last_t
        if elapsed < self._min_interval:
            return self.rates
        self.rates = tuple(max(0.0, c - lc) / _MIB / elapsed
                           for c, lc in zip(counters, last_counters, strict=True))
        self._last = (now, counters)
        return self.rates


class Metrics:
    """One domain of metrics (one device)."""

    def __init__(self):
        self.logger = LoggerConfig.setup_service_logger()

    @classmethod
    def keys(cls) -> frozenset[str]:
        """Widget keys exposed by this domain (one per ``metric_*`` method)."""
        return frozenset(name[len(_METRIC_PREFIX):] for name in dir(cls)
                         if name.startswith(_METRIC_PREFIX))

    def _prepare(self) -> None:
        """Hook run once before each collect (shared snapshot, rate updates)."""

    def collect(self) -> dict:
        """All values of the domain; a failing probe yields None, not an error."""
        try:
            self._prepare()
        except Exception as e:
            self.logger.debug(f"{type(self).__name__} prepare failed: {e}")
        out = {}
        for key in self.keys():
            try:
                out[key] = getattr(self, _METRIC_PREFIX + key)()
            except Exception as e:
                self.logger.debug(f"{key} unavailable: {e}")
                out[key] = None
        return out


import threading
import time

class MetricsCollector:
    DEFAULT_MAX_AGE = 10.0

    def __init__(
            self,
            providers: list[Metrics] | None = None,
            refresh_interval: float = DEFAULT_MAX_AGE,
            start_worker: bool = True,
    ):
        self.logger = LoggerConfig.setup_service_logger()

        if providers is None:
            providers = []
            for factory in _default_provider_factories():
                try:
                    providers.append(factory())
                except Exception as e:
                    self.logger.warning(
                        f"{factory.__name__} unavailable: {e}"
                    )

        self._providers = providers
        self._values: dict = {}
        self._ts = 0.0
        self._refresh_interval = refresh_interval

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._worker: threading.Thread | None = None

        # Produce a first snapshot before the UI starts rendering.
        self.refresh()

        if start_worker:
            self._worker = threading.Thread(
                target=self._refresh_loop,
                name="thermalright-metrics",
                daemon=True,
            )
            self._worker.start()

    def keys(self) -> frozenset[str]:
        out: frozenset[str] = frozenset()
        for provider in self._providers:
            out |= provider.keys()
        return out

    def collect(self) -> dict:
        out = {}
        for provider in self._providers:
            try:
                out.update(provider.collect())
            except Exception as e:
                self.logger.error(
                    f"{type(provider).__name__} collect failed: {e}"
                )
        return out

    def refresh(self) -> bool:
        """Collect off the render path and publish only when values changed."""
        try:
            new_values = self.collect()
        except Exception as e:
            self.logger.error(f"Metrics refresh failed: {e}")
            return False

        self._ts = time.monotonic()

        # Do not replace the snapshot when no displayed value changed.
        # This preserves the identity-based overlay invalidation contract.
        if new_values != self._values:
            self._values = new_values
            return True

        return False

    def _refresh_loop(self) -> None:
        while not self._stop_event.is_set():
            self.refresh()
            self._wake_event.wait(self._refresh_interval)
            self._wake_event.clear()

    def values(self, max_age: float = DEFAULT_MAX_AGE) -> dict:
        """Non-blocking render-path read of the last published snapshot."""
        return self._values

    def request_refresh(self) -> None:
        """Optional: ask the worker to refresh immediately."""
        self._wake_event.set()

    def close(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        self._wake_event.set()

        if self._worker is not None:
            self._worker.join(timeout=timeout)
            self._worker = None

def _default_provider_factories():
    # Local import: the providers subclass Metrics from this module.
    from thermalright_lcd_control.device_controller.metrics.cpu_metrics import CpuMetrics
    from thermalright_lcd_control.device_controller.metrics.disk import DiskMetrics
    from thermalright_lcd_control.device_controller.metrics.gpu_metrics import GpuMetrics
    from thermalright_lcd_control.device_controller.metrics.memory import MemoryMetrics
    from thermalright_lcd_control.device_controller.metrics.network import NetworkMetrics
    from thermalright_lcd_control.device_controller.metrics.system import SystemMetrics
    return (CpuMetrics, GpuMetrics, MemoryMetrics, DiskMetrics,
            NetworkMetrics, SystemMetrics)


_shared: MetricsCollector | None = None


def shared_collector() -> MetricsCollector:
    """Process-wide collector shared by every consumer (device engines + GUI).

    One set of sensors and one counter series for the rate metrics, so the
    preview and the devices always agree.
    """
    global _shared
    if _shared is None:
        _shared = MetricsCollector()
    return _shared
