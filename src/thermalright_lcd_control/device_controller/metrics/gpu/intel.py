# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Intel GPU metrics (i915 sysfs/hwmon, intel_gpu_top fallback).

Mixed into :class:`GpuMetrics`; relies on the shared state initialised there
(the ``_temp_*``/``_freq_*`` path caches, ``_intel_usage_cache``/
``_intel_usage_cache_time``/``_INTEL_USAGE_CACHE_TTL``, ``gpu_temp``/
``gpu_usage``/``gpu_freq``, ``logger``) and the shared ``_read_file_float`` helper.
"""
import glob
import json
import os
import subprocess
import time


class IntelMixin:
    def _is_intel_available(self):
        for vendor_file in glob.glob("/sys/class/drm/card*/device/vendor"):
            try:
                with open(vendor_file) as f:
                    if f.read().strip().lower() == "0x8086":
                        return True
            except Exception:
                continue
        try:
            r = subprocess.run(["intel_gpu_top", "-l"], capture_output=True, text=True, timeout=2)
            return r.returncode == 0
        except Exception:
            return False

    def _get_intel_name(self):
        return "Intel GPU"

    def _get_intel_temperature(self):
        # Use cache if available
        if self._temp_method_cache == "intel" and self._temp_path_cache:
            v = self._read_file_float(self._temp_path_cache, scale=1/1000.0)
            if v is not None:
                self.gpu_temp = v
                return v
            # Invalidate cache on failure
            self._temp_path_cache = None
            self._temp_method_cache = None

        try:
            for name_file in glob.glob("/sys/class/hwmon/hwmon*/name"):
                with open(name_file) as f:
                    if "i915" not in f.read().strip().lower():
                        continue
                base = os.path.dirname(name_file)
                for tin in glob.glob(os.path.join(base, "temp*_input")):
                    v = self._read_file_float(tin, scale=1/1000.0)
                    if v is not None:
                        self.gpu_temp = v
                        self._temp_path_cache = tin
                        self._temp_method_cache = "intel"
                        self.logger.debug(f"Intel GPU temperature: {v:.1f}°C")
                        return v
        except Exception:
            pass
        return None

    def _get_intel_usage(self):
        now = time.monotonic()
        if self._intel_usage_cache is not None and (now - self._intel_usage_cache_time) < self._INTEL_USAGE_CACHE_TTL:
            return self._intel_usage_cache
        try:
            r = subprocess.run(["intel_gpu_top", "-J", "-s", "100"],
                               capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                if "engines" in data:
                    vals = [float(eng["busy"]) for eng in data["engines"].values()
                            if isinstance(eng, dict) and "busy" in eng]
                    if vals:
                        self.gpu_usage = sum(vals) / len(vals)
                        self._intel_usage_cache = self.gpu_usage
                        self._intel_usage_cache_time = now
                        self.logger.debug(f"Intel GPU usage: {self.gpu_usage:.1f}%")
                        return self.gpu_usage
        except Exception:
            pass
        return None

    def _get_intel_frequency(self):
        # Use cache if available
        if self._freq_method_cache == "intel" and self._freq_path_cache:
            try:
                with open(self._freq_path_cache) as f:
                    self.gpu_freq = round(float(f.read().strip()), 2)
                    return self.gpu_freq
            except Exception:
                self._freq_path_cache = None
                self._freq_method_cache = None

        try:
            for p in glob.glob("/sys/class/drm/card*/gt_cur_freq_mhz"):
                with open(p) as f:
                    self.gpu_freq = round(float(f.read().strip()), 2)
                    self._freq_path_cache = p
                    self._freq_method_cache = "intel"
                    self.logger.debug(f"Intel GPU frequency: {self.gpu_freq} MHz")
                    return self.gpu_freq
        except Exception:
            pass
        return None
