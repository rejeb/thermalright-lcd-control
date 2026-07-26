# SPDX-License-Identifier: Apache-2.0
"""Socle métriques : découverte metric_*, tolérance aux pannes, collector
partagé et cache de values() (identité du dict entre deux rafraîchissements)."""
from unittest.mock import patch

import pytest

from thermalright_lcd_control.device_controller.metrics import base as base_mod
from thermalright_lcd_control.device_controller.metrics.base import (
    Metrics,
    MetricsCollector,
    shared_collector,
)


class _Fake(Metrics):
    def metric_alpha(self):
        return 1.0

    def metric_beta(self):
        return 2.0


class _Faulty(Metrics):
    def metric_ok(self):
        return 7.0

    def metric_broken(self):
        raise RuntimeError("boom")


class _BrokenInit(Metrics):
    def __init__(self):
        raise RuntimeError("no hardware")


# ── Metrics (base) ────────────────────────────────────────────────────────

def test_keys_discovers_metric_methods():
    assert _Fake.keys() == {"alpha", "beta"}


def test_collect_evaluates_every_key():
    assert _Fake().collect() == {"alpha": 1.0, "beta": 2.0}


def test_failing_probe_yields_none_without_breaking_others():
    assert _Faulty().collect() == {"ok": 7.0, "broken": None}


def test_prepare_failure_does_not_break_collect():
    class _BadPrepare(_Fake):
        def _prepare(self):
            raise RuntimeError("boom")

    assert _BadPrepare().collect() == {"alpha": 1.0, "beta": 2.0}


# ── MetricsCollector ──────────────────────────────────────────────────────

def test_collector_merges_providers():
    c = MetricsCollector(providers=[_Fake(), _Faulty()])
    assert c.collect() == {"alpha": 1.0, "beta": 2.0, "ok": 7.0, "broken": None}
    assert c.keys() == {"alpha", "beta", "ok", "broken"}


def test_collector_skips_provider_broken_at_init():
    with patch.object(base_mod, "_default_provider_factories",
                      return_value=(_Fake, _BrokenInit)):
        c = MetricsCollector()
    assert c.collect() == {"alpha": 1.0, "beta": 2.0}


def test_values_never_collects_on_the_render_path():
    """values() is a non-blocking read of the published snapshot.

    Collection happens in refresh(), off the render path, so repeated reads must
    never invoke a provider however much time passes.
    """
    calls = {"n": 0}

    class _Counting(Metrics):
        def metric_x(self):
            calls["n"] += 1
            return calls["n"]

    # start_worker=False: the background thread would collect concurrently and
    # make the call count non-deterministic.
    c = MetricsCollector(providers=[_Counting()], start_worker=False)
    after_init = calls["n"]                    # __init__ publishes a first snapshot

    with patch("time.monotonic", return_value=100.0):
        c.values()
    with patch("time.monotonic", return_value=1_000.0):
        c.values()
    assert calls["n"] == after_init            # reads never collect

    c.refresh()
    assert calls["n"] == after_init + 1        # only refresh() collects


def test_refresh_keeps_dict_identity_when_values_are_unchanged():
    """Identity is the overlay-invalidation signal.

    refresh() must publish a NEW dict only when a displayed value actually
    changed; an unchanged collection keeps the same object so the overlay is not
    needlessly redrawn.
    """
    c = MetricsCollector(providers=[_Fake()], start_worker=False)
    first = c.values()                         # snapshot published by __init__

    assert c.refresh() is False                # _Fake is constant → nothing changed
    assert c.values() is first                 # same object → no invalidation


def test_refresh_publishes_new_dict_when_a_value_changes():
    counter = {"n": 0}

    class _Changing(Metrics):
        def metric_x(self):
            counter["n"] += 1
            return counter["n"]

    c = MetricsCollector(providers=[_Changing()], start_worker=False)
    first = c.values()

    assert c.refresh() is True                 # value changed
    assert c.values() is not first             # new object → invalidation
    assert c.values() != first


def test_shared_collector_is_a_singleton():
    with patch.object(base_mod, "_default_provider_factories",
                      return_value=(_Fake,)), \
            patch.object(base_mod, "_shared", None):
        a = shared_collector()
        b = shared_collector()
        assert a is b


# ── cohérence avec le catalogue GUI ───────────────────────────────────────

def test_gui_catalog_matches_collector_keys():
    """Chaque métrique du catalogue/palette est fournie par un provider, et
    chaque clé widget des providers est exposée dans la GUI."""
    pytest.importorskip("PySide6")
    from thermalright_lcd_control.device_controller.metrics.cpu_metrics import CpuMetrics
    from thermalright_lcd_control.device_controller.metrics.disk import DiskMetrics
    from thermalright_lcd_control.device_controller.metrics.gpu_metrics import GpuMetrics
    from thermalright_lcd_control.device_controller.metrics.memory import MemoryMetrics
    from thermalright_lcd_control.device_controller.metrics.network import NetworkMetrics
    from thermalright_lcd_control.device_controller.metrics.system import SystemMetrics
    from thermalright_lcd_control.gui.native.overlay import model
    from thermalright_lcd_control.gui.native.overlay.palette import _TILES

    provider_keys: set[str] = set()
    for cls in (CpuMetrics, GpuMetrics, MemoryMetrics, DiskMetrics,
                NetworkMetrics, SystemMetrics):
        provider_keys |= cls.keys()

    catalog = set(model.METRICS)
    tiles = {key for wtype, key, *_ in _TILES if wtype == "metric"}

    # tout ce que la GUI propose existe côté providers
    assert catalog <= provider_keys
    assert tiles == catalog
    assert catalog <= set(model.METRIC_NAMES)
    # toutes les clés widget des providers sont dans le catalogue
    # (gpu_vendor/gpu_name sont informatives, pas des widgets)
    assert provider_keys - {"gpu_vendor", "gpu_name"} == catalog
