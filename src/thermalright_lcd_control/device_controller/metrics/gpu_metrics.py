# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025

import glob
import json
import os
import re
import subprocess

from . import Metrics
from ...common.logging_config import LoggerConfig


class GpuMetrics(Metrics):
    """
    AMD-friendly GPU metrics:
      - Detect vendor via sysfs; still supports NVIDIA (nvidia-smi) & Intel.
      - AMD temperature: hwmon 'amdgpu' (prefers junction/hotspot, else edge).
      - AMD usage: /sys/class/drm/card*/device/gpu_busy_percent (no root).
      - AMD frequency: prefer pp_dpm_sclk (* line), else hwmon freq1_input, else debugfs amdgpu_pm_info.
    """
    def __init__(self):
        super().__init__()
        self.logger = LoggerConfig.setup_service_logger()
        self.gpu_temp = None
        self.gpu_usage = None
        self.gpu_freq = None
        self.gpu_vendor = None
        self.gpu_name = None

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
                self.gpu_name = self._get_amd_name()
                self.logger.info(f"AMD GPU detected: {self.gpu_name}")
                return
            if self._is_intel_available():
                self.gpu_vendor = "intel"
                self.gpu_name = self._get_intel_name()
                self.logger.info(f"Intel GPU detected: {self.gpu_name}")
                return
            self.logger.warning("No supported GPU detected")
        except Exception as e:
            self.logger.error(f"Error detecting GPU: {e}")

    def _is_nvidia_available(self):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4
            )
            return r.returncode == 0 and r.stdout.strip()
        except Exception:
            return False

    def _is_amd_available(self):
        # sysfs vendor check
        for vendor_file in glob.glob("/sys/class/drm/card*/device/vendor"):
            try:
                with open(vendor_file) as f:
                    if f.read().strip().lower() == "0x1002":
                        return True
            except Exception:
                continue
        # rocm-smi availability (optional)
        try:
            r = subprocess.run(["rocm-smi", "--showid"], capture_output=True, text=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

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

    # ---------- names ----------

    def _get_nvidia_name(self):
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

    def _get_amd_name(self):
        # Try rocm-smi product name
        try:
            r = subprocess.run(["rocm-smi", "--showproductname"],
                               capture_output=True, text=True, timeout=4)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "Card series:" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
        # Fallback: sysfs device id
        for dev_path in glob.glob("/sys/class/drm/card*/device"):
            try:
                with open(os.path.join(dev_path, "vendor")) as f:
                    if f.read().strip().lower() != "0x1002":
                        continue
                with open(os.path.join(dev_path, "device")) as f:
                    devid = f.read().strip()
                return f"AMD GPU (Device {devid})"
            except Exception:
                continue
        return "AMD GPU"

    def _get_intel_name(self):
        return "Intel GPU"

    # ---------- temperatures ----------

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

    def _get_nvidia_temperature(self):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4
            )
            if r.returncode == 0 and r.stdout.strip():
                self.gpu_temp = float(r.stdout.strip().splitlines()[0])
                self.logger.debug(f"NVIDIA GPU temperature: {self.gpu_temp}°C")
                return self.gpu_temp
        except Exception:
            pass
        return None

    def _amd_hwmon_temp(self):
        """
        Prefer 'junction'/'hotspot' label if present, else 'edge'.
        temp*_input is millidegrees.
        """
        for name_file in glob.glob("/sys/class/hwmon/hwmon*/name"):
            try:
                with open(name_file) as f:
                    if "amdgpu" not in f.read().strip().lower():
                        continue
                base = os.path.dirname(name_file)
                labels = {}
                for lbl in glob.glob(os.path.join(base, "temp*_label")):
                    m = re.search(r"temp(\d+)_label$", lbl)
                    if not m:
                        continue
                    idx = m.group(1)
                    try:
                        with open(lbl) as f:
                            labels[idx] = f.read().strip().lower()
                    except Exception:
                        pass

                # pick best
                pick = None
                for idx, lab in labels.items():
                    if any(k in lab for k in ("junction", "hotspot", "tjunction")):
                        pick = idx
                        break
                if not pick:
                    for idx, lab in labels.items():
                        if "edge" in lab:
                            pick = idx
                            break

                if pick:
                    p = os.path.join(base, f"temp{pick}_input")
                    if os.path.exists(p):
                        v = self._read_file_float(p, scale=1/1000.0)
                        if v is not None:
                            return v

                # fallback: first temp*_input
                inputs = sorted(glob.glob(os.path.join(base, "temp*_input")))
                if inputs:
                    v = self._read_file_float(inputs[0], scale=1/1000.0)
                    if v is not None:
                        return v
            except Exception:
                continue
        return None

    def _read_file_float(self, path, scale=1.0):
        try:
            with open(path) as f:
                return float(f.read().strip()) * scale
        except Exception:
            return None

    def _get_amd_temperature(self):
        # 1) hwmon
        v = self._amd_hwmon_temp()
        if v is not None:
            self.gpu_temp = v
            self.logger.debug(f"AMD GPU temperature (hwmon): {v:.1f}°C")
            return v
        # 2) rocm-smi
        try:
            r = subprocess.run(["rocm-smi", "--showtemp"],
                               capture_output=True, text=True, timeout=4)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "Temperature:" in line:
                        s = line.split(":", 1)[1].strip().lower().replace("°c", "").replace("c", "")
                        self.gpu_temp = float(s)
                        self.logger.debug(f"AMD GPU temperature (rocm-smi): {self.gpu_temp}°C")
                        return self.gpu_temp
        except Exception:
            pass
        return None

    def _get_intel_temperature(self):
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
                        self.logger.debug(f"Intel GPU temperature: {v:.1f}°C")
                        return v
        except Exception:
            pass
        return None

    # ---------- usage ----------

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

    def _get_nvidia_usage(self):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4
            )
            if r.returncode == 0 and r.stdout.strip():
                self.gpu_usage = float(r.stdout.strip().splitlines()[0])
                self.logger.debug(f"NVIDIA GPU usage: {self.gpu_usage:.1f}%")
                return self.gpu_usage
        except Exception:
            pass
        return None

    def _get_amd_usage(self):
        """
        amdgpu exposes instantaneous busy percent:
          /sys/class/drm/card*/device/gpu_busy_percent  (0..100)
        """
        for p in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
            try:
                with open(p) as f:
                    self.gpu_usage = float(f.read().strip())
                    self.logger.debug(f"AMD GPU usage: {self.gpu_usage:.1f}% (from {p})")
                    return self.gpu_usage
            except Exception:
                continue
        # rocm-smi fallback
        try:
            r = subprocess.run(["rocm-smi", "--showuse"],
                               capture_output=True, text=True, timeout=4)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "GPU use (%)" in line:
                        s = line.split(":", 1)[1].strip().replace("%", "")
                        self.gpu_usage = float(s)
                        self.logger.debug(f"AMD GPU usage (rocm-smi): {self.gpu_usage:.1f}%")
                        return self.gpu_usage
        except Exception:
            pass
        return None

    def _get_intel_usage(self):
        try:
            r = subprocess.run(["intel_gpu_top", "-J", "-s", "1000"],
                               capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                if "engines" in data:
                    vals = []
                    for eng in data["engines"].values():
                        if isinstance(eng, dict) and "busy" in eng:
                            vals.append(float(eng["busy"]))
                    if vals:
                        self.gpu_usage = sum(vals) / len(vals)
                        self.logger.debug(f"Intel GPU usage: {self.gpu_usage:.1f}%")
                        return self.gpu_usage
        except Exception:
            pass
        return None

    # ---------- frequency ----------

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

    def _get_nvidia_frequency(self):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=clocks.current.graphics", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4
            )
            if r.returncode == 0 and r.stdout.strip():
                self.gpu_freq = round(float(r.stdout.strip().splitlines()[0]), 2)
                self.logger.debug(f"NVIDIA GPU frequency: {self.gpu_freq:.2f} MHz")
                return self.gpu_freq
        except Exception:
            pass
        return None

    def _amd_freq_from_pp_dpm(self, card_dev_dir):
        p = os.path.join(card_dev_dir, "pp_dpm_sclk")
        try:
            with open(p) as f:
                # lines like: "0: 300Mhz", "1: 500Mhz *"
                current = None
                for line in f:
                    if "*" in line:
                        current = line
                        break
                if not current:
                    return None
                mhz = re.search(r"(\d+)\s*MHz", current, re.IGNORECASE)
                if mhz:
                    return float(mhz.group(1))
        except Exception:
            pass
        return None

    def _amd_freq_from_hwmon(self):
        # some kernels expose freq1_input (Hz) under amdgpu hwmon
        for name_file in glob.glob("/sys/class/hwmon/hwmon*/name"):
            try:
                with open(name_file) as f:
                    if "amdgpu" not in f.read().strip().lower():
                        continue
                base = os.path.dirname(name_file)
                f1 = os.path.join(base, "freq1_input")
                if os.path.exists(f1):
                    hz = self._read_file_float(f1, scale=1.0)
                    if hz and hz > 0:
                        return round(hz / 1_000_000.0, 2)  # Hz → MHz
            except Exception:
                continue
        return None

    def _amd_freq_from_debugfs(self):
        # fallback: /sys/kernel/debug/dri/*/amdgpu_pm_info (root or readable systems)
        for info in glob.glob("/sys/kernel/debug/dri/*/amdgpu_pm_info"):
            try:
                with open(info) as f:
                    txt = f.read()
                m = re.search(r"GPU\s+clock:\s+(\d+)\s*MHz", txt, re.IGNORECASE)
                if m:
                    return float(m.group(1))
            except Exception:
                continue
        return None

    def _get_amd_frequency(self):
        # locate the card device dir
        for card in sorted(glob.glob("/sys/class/drm/card*/device")):
            try:
                with open(os.path.join(card, "vendor")) as f:
                    if f.read().strip().lower() != "0x1002":
                        continue
                # 1) pp_dpm_sclk
                v = self._amd_freq_from_pp_dpm(card)
                if v:
                    self.gpu_freq = round(v, 2)
                    self.logger.debug(f"AMD GPU freq (pp_dpm_sclk): {self.gpu_freq} MHz")
                    return self.gpu_freq
                # 2) hwmon freq1_input
                v = self._amd_freq_from_hwmon()
                if v:
                    self.gpu_freq = v
                    self.logger.debug(f"AMD GPU freq (hwmon): {self.gpu_freq} MHz")
                    return self.gpu_freq
                # 3) debugfs amdgpu_pm_info
                v = self._amd_freq_from_debugfs()
                if v:
                    self.gpu_freq = v
                    self.logger.debug(f"AMD GPU freq (debugfs): {self.gpu_freq} MHz")
                    return self.gpu_freq
            except Exception:
                continue
        return None

    def _get_intel_frequency(self):
        try:
            for p in glob.glob("/sys/class/drm/card*/gt_cur_freq_mhz"):
                with open(p) as f:
                    self.gpu_freq = round(float(f.read().strip()), 2)
                    self.logger.debug(f"Intel GPU frequency: {self.gpu_freq} MHz")
                    return self.gpu_freq
        except Exception:
            pass
        return None

    # ---------- bundles ----------

    def get_all_metrics(self):
        self.logger.debug("Collecting all GPU metrics")
        if self.gpu_vendor is None:
            return {'vendor': None, 'name': None, 'temperature': None, 'usage_percentage': None, 'frequency': None}
        return {
            'vendor': self.gpu_vendor,
            'name': self.gpu_name,
            'temperature': self.get_temperature(),
            'usage_percentage': self.get_usage_percentage(),
            'frequency': self.get_frequency()
        }

    def get_metric_value(self, metric_name) -> str:
        if metric_name == "gpu_temperature":
            v = self.get_temperature(); return f"{v}" if v is not None else "N/A"
        if metric_name == "gpu_usage":
            v = self.get_usage_percentage(); return f"{v}" if v is not None else "N/A"
        if metric_name == "gpu_frequency":
            v = self.get_frequency(); return f"{v}" if v is not None else "N/A"
        return "N/A"

    def __str__(self):
        if self.gpu_vendor is None:
            return "GPU - No supported GPU detected"
        t = self.get_temperature()
        u = self.get_usage_percentage()
        f = self.get_frequency()
        t_s = f"{t:.1f}°C" if t is not None else "N/A"
        u_s = f"{u:.1f}%" if u is not None else "N/A"
        f_s = f"{f:.0f} MHz" if f is not None else "N/A"
        return f"GPU ({self.gpu_name}) - Usage: {u_s}, Temperature: {t_s}, Frequency: {f_s}"
