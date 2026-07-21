# SPDX-License-Identifier: Apache-2.0
"""Providers de métriques par périphérique (memory / disk / network / system)."""
from collections import namedtuple
from unittest.mock import patch

import pytest

from thermalright_lcd_control.device_controller.metrics.disk import DiskMetrics
from thermalright_lcd_control.device_controller.metrics.memory import MemoryMetrics
from thermalright_lcd_control.device_controller.metrics.network import NetworkMetrics
from thermalright_lcd_control.device_controller.metrics.system import SystemMetrics

VMem = namedtuple("VMem", "percent used available")
Swap = namedtuple("Swap", "percent total")
DiskUsage = namedtuple("DiskUsage", "percent")
DiskIO = namedtuple("DiskIO", "read_bytes write_bytes")
NetIO = namedtuple("NetIO", "bytes_recv bytes_sent")

_GIB = 1024 ** 3
_MIB = 1024 ** 2


# ── memory ────────────────────────────────────────────────────────────────

def test_memory_keys():
    assert MemoryMetrics.keys() == {
        "memory_usage", "memory_used", "memory_available", "swap_usage"}


def test_memory_metrics():
    vmem = VMem(percent=42.5, used=8 * _GIB, available=24 * _GIB)
    with patch("psutil.virtual_memory", return_value=vmem), \
            patch("psutil.swap_memory", return_value=Swap(percent=12.0, total=_GIB)):
        data = MemoryMetrics().collect()
    assert data["memory_usage"] == 42.5
    assert data["memory_used"] == pytest.approx(8.0)
    assert data["memory_available"] == pytest.approx(24.0)
    assert data["swap_usage"] == 12.0


def test_swap_usage_none_without_swap():
    vmem = VMem(percent=10.0, used=_GIB, available=_GIB)
    with patch("psutil.virtual_memory", return_value=vmem), \
            patch("psutil.swap_memory", return_value=Swap(percent=0.0, total=0)):
        assert MemoryMetrics().collect()["swap_usage"] is None


def test_memory_errors_yield_none():
    with patch("psutil.virtual_memory", side_effect=OSError("boom")), \
            patch("psutil.swap_memory", side_effect=OSError("boom")):
        data = MemoryMetrics().collect()
    assert data == {"memory_usage": None, "memory_used": None,
                    "memory_available": None, "swap_usage": None}


# ── disk ──────────────────────────────────────────────────────────────────

def test_disk_keys():
    assert DiskMetrics.keys() == {
        "disk_usage", "disk_read_speed", "disk_write_speed"}


def test_disk_usage_reads_configured_path():
    m = DiskMetrics()
    with patch("psutil.disk_usage", return_value=DiskUsage(percent=58.3)) as du, \
            patch("psutil.disk_io_counters", return_value=None):
        assert m.collect()["disk_usage"] == 58.3
        du.assert_called_once_with("/")


def test_disk_rates_first_collect_is_zero():
    m = DiskMetrics()
    with patch("psutil.disk_io_counters",
               return_value=DiskIO(read_bytes=1000, write_bytes=500)), \
            patch("psutil.disk_usage", return_value=DiskUsage(percent=0.0)):
        data = m.collect()
    assert data["disk_read_speed"] == 0.0
    assert data["disk_write_speed"] == 0.0


def test_disk_rates_from_counter_delta():
    m = DiskMetrics()
    with patch("psutil.disk_usage", return_value=DiskUsage(percent=0.0)):
        with patch("psutil.disk_io_counters",
                   return_value=DiskIO(read_bytes=0, write_bytes=0)), \
                patch("time.monotonic", return_value=100.0):
            m.collect()                          # premier échantillon
        with patch("psutil.disk_io_counters",
                   return_value=DiskIO(read_bytes=10 * _MIB, write_bytes=5 * _MIB)), \
                patch("time.monotonic", return_value=102.0):
            data = m.collect()
    assert data["disk_read_speed"] == pytest.approx(5.0)
    assert data["disk_write_speed"] == pytest.approx(2.5)


def test_disk_rates_keep_previous_below_min_interval():
    m = DiskMetrics()
    with patch("psutil.disk_usage", return_value=DiskUsage(percent=0.0)):
        with patch("psutil.disk_io_counters",
                   return_value=DiskIO(read_bytes=0, write_bytes=0)), \
                patch("time.monotonic", return_value=100.0):
            m.collect()
        with patch("psutil.disk_io_counters",
                   return_value=DiskIO(read_bytes=_MIB, write_bytes=_MIB)), \
                patch("time.monotonic", return_value=100.1):
            data = m.collect()                   # pas recalculé (< 0.5s)
    assert data["disk_read_speed"] == 0.0


# ── network ───────────────────────────────────────────────────────────────

def test_network_keys():
    assert NetworkMetrics.keys() == {"net_download_speed", "net_upload_speed"}


def test_net_rates_from_counter_delta():
    m = NetworkMetrics()
    with patch("psutil.net_io_counters",
               return_value=NetIO(bytes_recv=0, bytes_sent=0)), \
            patch("time.monotonic", return_value=50.0):
        m.collect()
    with patch("psutil.net_io_counters",
               return_value=NetIO(bytes_recv=4 * _MIB, bytes_sent=2 * _MIB)), \
            patch("time.monotonic", return_value=52.0):
        data = m.collect()
    assert data["net_download_speed"] == pytest.approx(2.0)
    assert data["net_upload_speed"] == pytest.approx(1.0)


def test_net_rates_never_negative_after_counter_reset():
    m = NetworkMetrics()
    with patch("psutil.net_io_counters",
               return_value=NetIO(bytes_recv=10 * _MIB, bytes_sent=10 * _MIB)), \
            patch("time.monotonic", return_value=50.0):
        m.collect()
    with patch("psutil.net_io_counters",
               return_value=NetIO(bytes_recv=0, bytes_sent=0)), \
            patch("time.monotonic", return_value=52.0):
        data = m.collect()
    assert data["net_download_speed"] == 0.0
    assert data["net_upload_speed"] == 0.0


def test_net_rates_survive_psutil_error():
    m = NetworkMetrics()
    with patch("psutil.net_io_counters", side_effect=OSError("boom")):
        data = m.collect()
    assert data["net_download_speed"] == 0.0


# ── system ────────────────────────────────────────────────────────────────

def test_system_keys():
    assert SystemMetrics.keys() == {"uptime", "load_avg", "process_count"}


def test_system_metrics():
    with patch("psutil.boot_time", return_value=1000.0), \
            patch("time.time", return_value=1000.0 + 7200.0), \
            patch("psutil.getloadavg", return_value=(1.25, 0.8, 0.5)), \
            patch("psutil.pids", return_value=list(range(312))):
        data = SystemMetrics().collect()
    assert data["uptime"] == pytest.approx(2.0)
    assert data["load_avg"] == 1.25
    assert data["process_count"] == 312


def test_system_errors_yield_none():
    with patch("psutil.boot_time", side_effect=OSError("boom")), \
            patch("psutil.getloadavg", side_effect=OSError("boom")), \
            patch("psutil.pids", side_effect=OSError("boom")):
        data = SystemMetrics().collect()
    assert data == {"uptime": None, "load_avg": None, "process_count": None}
