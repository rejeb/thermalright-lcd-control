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


def test_values_caches_and_keeps_dict_identity():
    c = MetricsCollector(providers=[_Fake()])
    with patch("time.monotonic", return_value=100.0):
        first = c.values(max_age=10.0)
    with patch("time.monotonic", return_value=105.0):
        again = c.values(max_age=10.0)
    assert again is first                      # même objet → pas de refresh
    with patch("time.monotonic", return_value=111.0):
        fresh = c.values(max_age=10.0)
    assert fresh is not first                  # nouvel objet → refresh détectable
    assert fresh == first


def test_values_respects_caller_max_age():
    calls = {"n": 0}

    class _Counting(Metrics):
        def metric_x(self):
            calls["n"] += 1
            return calls["n"]

    c = MetricsCollector(providers=[_Counting()])
    with patch("time.monotonic", return_value=100.0):
        c.values(max_age=1.0)
    with patch("time.monotonic", return_value=100.5):
        c.values(max_age=1.0)                  # frais → pas de collecte
    assert calls["n"] == 1
    with patch("time.monotonic", return_value=101.5):
        c.values(max_age=1.0)                  # périmé → collecte
    assert calls["n"] == 2


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
