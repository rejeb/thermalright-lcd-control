# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""NVIDIA GPU metrics (pynvml first, nvidia-smi fallback).

Mixed into :class:`GpuMetrics`; relies on the shared state initialised there
(``_nvml_handle``, ``_nvidia_cache``/``_nvidia_cache_time``/``_NVIDIA_CACHE_TTL``,
``gpu_temp``/``gpu_usage``/``gpu_freq``, ``logger``).
"""
import subprocess
import time

try:
    import pynvml as _pynvml
    _HAS_PYNVML = True
except ImportError:
    _pynvml = None
    _HAS_PYNVML = False


class NvidiaMixin:
    def _is_nvidia_available(self):
        if _HAS_PYNVML:
            try:
                _pynvml.nvmlInit()
                if _pynvml.nvmlDeviceGetCount() > 0:
                    self._nvml_handle = _pynvml.nvmlDeviceGetHandleByIndex(0)
                    return True
            except Exception:
                pass
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4
            )
            return r.returncode == 0 and r.stdout.strip()
        except Exception:
            return False

    def _get_nvidia_name(self):
        if _HAS_PYNVML and self._nvml_handle is not None:
            try:
                name = _pynvml.nvmlDeviceGetName(self._nvml_handle)
                if isinstance(name, bytes):
                    name = name.decode()
                return str(name)
            except Exception:
                pass
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()[0]
        except Exception:
            pass
        return "NVIDIA GPU"

    def _get_nvidia_all(self) -> dict | None:
        """Batch all NVIDIA metrics in a single call, cached for _NVIDIA_CACHE_TTL seconds."""
        now = time.monotonic()
        if self._nvidia_cache is not None and (now - self._nvidia_cache_time) < self._NVIDIA_CACHE_TTL:
            return self._nvidia_cache

        if _HAS_PYNVML and self._nvml_handle is not None:
            try:
                temp = float(_pynvml.nvmlDeviceGetTemperature(
                    self._nvml_handle, _pynvml.NVML_TEMPERATURE_GPU))
                util = _pynvml.nvmlDeviceGetUtilizationRates(self._nvml_handle)
                clock = float(_pynvml.nvmlDeviceGetClockInfo(
                    self._nvml_handle, _pynvml.NVML_CLOCK_GRAPHICS))
                self._nvidia_cache = {
                    "temperature": temp,
                    "usage":       float(util.gpu),
                    "frequency":   clock,
                }
                self._nvidia_cache_time = now
                return self._nvidia_cache
            except Exception:
                pass

        try:
            r = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=temperature.gpu,utilization.gpu,clocks.current.graphics",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().splitlines()[0].split(",")
                if len(parts) >= 3:
                    self._nvidia_cache = {
                        "temperature": float(parts[0].strip()),
                        "usage":       float(parts[1].strip()),
                        "frequency":   float(parts[2].strip()),
                    }
                    self._nvidia_cache_time = now
                    return self._nvidia_cache
        except Exception:
            pass
        self._nvidia_cache = None
        return None

    def _get_nvidia_temperature(self):
        data = self._get_nvidia_all()
        if data:
            self.gpu_temp = data["temperature"]
            self.logger.debug(f"NVIDIA GPU temperature: {self.gpu_temp}°C")
            return self.gpu_temp
        return None

    def _get_nvidia_usage(self):
        data = self._get_nvidia_all()
        if data:
            self.gpu_usage = data["usage"]
            self.logger.debug(f"NVIDIA GPU usage: {self.gpu_usage:.1f}%")
            return self.gpu_usage
        return None

    def _get_nvidia_frequency(self):
        data = self._get_nvidia_all()
        if data:
            self.gpu_freq = round(data["frequency"], 2)
            self.logger.debug(f"NVIDIA GPU frequency: {self.gpu_freq:.2f} MHz")
            return self.gpu_freq
        return None
