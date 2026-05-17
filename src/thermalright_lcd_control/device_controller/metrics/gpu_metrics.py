# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025

from thermalright_lcd_control.device_controller.metrics.base import Metrics, read_sysfs_float
from thermalright_lcd_control.device_controller.metrics.gpu import (
    AmdMixin,
    IntelMixin,
    NvidiaMixin,
)


class GpuMetrics(NvidiaMixin, AmdMixin, IntelMixin, Metrics):
    """
    AMD-friendly GPU metrics:
      - Detect vendor via sysfs; still supports NVIDIA (nvidia-smi) & Intel.
      - On AMD: prefer a discrete GPU first, then fallback to iGPU.
      - AMD temperature: hwmon for the *selected* card (junction/hotspot, else edge).
      - AMD usage: /sys/class/drm/cardX/device/gpu_busy_percent (selected card).
      - AMD frequency: prefer pp_dpm_sclk on selected card, else that card's hwmon freq1_input, else debugfs match by BDF.

    Vendor-specific collection lives in the per-vendor mixins
    (:class:`NvidiaMixin`, :class:`AmdMixin`, :class:`IntelMixin`); this class owns
    the shared state, vendor detection and the public metric surface.
    """
    def __init__(self):
        super().__init__()
        self.gpu_temp = None
        self.gpu_usage = None
        self.gpu_freq = None
        self.gpu_vendor = None
        self.gpu_name = None

        # AMD selection state (only used when gpu_vendor == "amd")
        self.amd_card_path = None          # /sys/class/drm/cardX/device
        self.amd_card_index = None         # X
        self.amd_pci_bdf = None            # e.g., "0000:65:00.0"
        self.amd_hwmon_base = None         # /sys/class/hwmon/hwmonY

        # pynvml handle (set during detection when pynvml is available)
        self._nvml_handle = None

        # Batched NVIDIA cache (avoids repeated calls per refresh cycle)
        self._nvidia_cache: dict | None = None
        self._nvidia_cache_time: float = 0.0
        self._NVIDIA_CACHE_TTL: float = 10.0

        # Intel usage cache (intel_gpu_top is a blocking subprocess)
        self._intel_usage_cache: float | None = None
        self._intel_usage_cache_time: float = 0.0
        self._INTEL_USAGE_CACHE_TTL: float = 10.0

        # Cache to optimize performance (AMD / Intel)
        self._temp_path_cache = None
        self._temp_method_cache = None
        self._usage_path_cache = None
        self._freq_path_cache = None
        self._freq_method_cache = None

        self.logger.debug("GpuMetrics initialized")
        self._detect_gpu()

    # ---------- detection ----------

    def _detect_gpu(self):
        try:
            if self._is_nvidia_available():
                self.gpu_vendor = "nvidia"
                self.gpu_name = self._get_nvidia_name()
                self.logger.info(f"NVIDIA GPU detected: {self.gpu_name}")
                return

            if self._is_amd_available():
                self.gpu_vendor = "amd"
                self._select_amd_card()  # <-- choose dGPU first, else iGPU
                self.gpu_name = self._get_amd_name()
                chosen = f"AMD GPU detected: {self.gpu_name}"
                if self.amd_card_index is not None and self.amd_pci_bdf:
                    chosen += f" [card{self.amd_card_index} @ {self.amd_pci_bdf}]"
                self.logger.info(chosen)
                return

            if self._is_intel_available():
                self.gpu_vendor = "intel"
                self.gpu_name = self._get_intel_name()
                self.logger.info(f"Intel GPU detected: {self.gpu_name}")
                return

            self.logger.warning("No supported GPU detected")
        except Exception as e:
            self.logger.error(f"Error detecting GPU: {e}")

    # ---------- shared helper ----------

    def _read_file_float(self, path, scale=1.0):
        return read_sysfs_float(path, scale)

    # ---------- dispatchers ----------

    def get_temperature(self):
        try:
            if self.gpu_vendor == "nvidia":
                return self._get_nvidia_temperature()
            if self.gpu_vendor == "amd":
                return self._get_amd_temperature()
            if self.gpu_vendor == "intel":
                return self._get_intel_temperature()
            self.logger.warning("No GPU detected for temperature")
            return None
        except Exception as e:
            self.logger.error(f"Error reading GPU temperature: {e}")
            return None

    def get_usage_percentage(self):
        try:
            if self.gpu_vendor == "nvidia":
                return self._get_nvidia_usage()
            if self.gpu_vendor == "amd":
                return self._get_amd_usage()
            if self.gpu_vendor == "intel":
                return self._get_intel_usage()
            self.logger.warning("No GPU detected for usage")
            return None
        except Exception as e:
            self.logger.error(f"Error reading GPU usage: {e}")
            return None

    def get_frequency(self):
        try:
            if self.gpu_vendor == "nvidia":
                return self._get_nvidia_frequency()
            if self.gpu_vendor == "amd":
                return self._get_amd_frequency()
            if self.gpu_vendor == "intel":
                return self._get_intel_frequency()
            self.logger.warning("No GPU detected for frequency")
            return None
        except Exception as e:
            self.logger.error(f"Error reading GPU frequency: {e}")
            return None

    # ---------- widget keys ----------
    # NVIDIA stays batched: the three dispatchers all read the same TTL-cached
    # ``_get_nvidia_all()`` snapshot, so one collect = one query.

    def metric_gpu_temperature(self):
        return self.get_temperature()

    def metric_gpu_usage(self):
        return self.get_usage_percentage()

    def metric_gpu_frequency(self):
        return self.get_frequency()

    def metric_gpu_vendor(self):
        return self.gpu_vendor

    def metric_gpu_name(self):
        return self.gpu_name
