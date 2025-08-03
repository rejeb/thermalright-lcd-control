# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import glob
import json
import os
import subprocess

from . import Metrics
from ...common.logging_config import LoggerConfig


class GpuMetrics(Metrics):
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

    def _detect_gpu(self):
        """Detect GPU vendor and model"""
        try:
            # Try to detect NVIDIA GPU
            if self._is_nvidia_available():
                self.gpu_vendor = "nvidia"
                self.gpu_name = self._get_nvidia_name()
                self.logger.info(f"NVIDIA GPU detected: {self.gpu_name}")
                return

            # Try to detect AMD GPU
            if self._is_amd_available():
                self.gpu_vendor = "amd"
                self.gpu_name = self._get_amd_name()
                self.logger.info(f"AMD GPU detected: {self.gpu_name}")
                return

            # Try to detect Intel GPU
            if self._is_intel_available():
                self.gpu_vendor = "intel"
                self.gpu_name = self._get_intel_name()
                self.logger.info(f"Intel GPU detected: {self.gpu_name}")
                return

            self.logger.warning("No supported GPU detected")

        except Exception as e:
            self.logger.error(f"Error detecting GPU: {e}")

    def _is_nvidia_available(self):
        """Check if NVIDIA GPU and nvidia-smi are available"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=5)
            return result.returncode == 0 and result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _is_amd_available(self):
        """Check if AMD GPU is available"""
        # Check for AMD GPU via sysfs
        amd_gpu_paths = glob.glob('/sys/class/drm/card*/device/vendor')
        for vendor_file in amd_gpu_paths:
            try:
                with open(vendor_file, 'r') as f:
                    vendor_id = f.read().strip()
                    if vendor_id == '0x1002':  # AMD vendor ID
                        return True
            except (IOError, OSError):
                continue

        # Check for rocm-smi
        try:
            result = subprocess.run(['rocm-smi', '--showid'],
                                    capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return False

    def _is_intel_available(self):
        """Check if Intel GPU is available"""
        # Check for Intel GPU via sysfs
        intel_gpu_paths = glob.glob('/sys/class/drm/card*/device/vendor')
        for vendor_file in intel_gpu_paths:
            try:
                with open(vendor_file, 'r') as f:
                    vendor_id = f.read().strip()
                    if vendor_id == '0x8086':  # Intel vendor ID
                        return True
            except (IOError, OSError):
                continue

        # Check for intel_gpu_top
        try:
            result = subprocess.run(['intel_gpu_top', '-l'],
                                    capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return False

    def _get_nvidia_name(self):
        """Get NVIDIA GPU name"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception as e:
            self.logger.debug(f"Could not get NVIDIA GPU name: {e}")
        return "NVIDIA GPU"

    def _get_amd_name(self):
        """Get AMD GPU name"""
        try:
            # Try with rocm-smi first
            result = subprocess.run(['rocm-smi', '--showproductname'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'Card series:' in line:
                        return line.split(':')[1].strip()
        except Exception:
            pass

        # Fallback: read from sysfs
        try:
            amd_gpu_paths = glob.glob('/sys/class/drm/card*/device')
            for device_path in amd_gpu_paths:
                vendor_file = os.path.join(device_path, 'vendor')
                if os.path.exists(vendor_file):
                    with open(vendor_file, 'r') as f:
                        if f.read().strip() == '0x1002':  # AMD
                            device_file = os.path.join(device_path, 'device')
                            if os.path.exists(device_file):
                                with open(device_file, 'r') as f:
                                    device_id = f.read().strip()
                                    return f"AMD GPU (Device ID: {device_id})"
        except Exception as e:
            self.logger.debug(f"Could not get AMD GPU name: {e}")

        return "AMD GPU"

    def _get_intel_name(self):
        """Get Intel GPU name"""
        # Intel GPU name detection is more complex, return generic name
        return "Intel GPU"

    def get_temperature(self):
        """Get GPU temperature in Celsius"""
        try:
            if self.gpu_vendor == "nvidia":
                return self._get_nvidia_temperature()
            elif self.gpu_vendor == "amd":
                return self._get_amd_temperature()
            elif self.gpu_vendor == "intel":
                return self._get_intel_temperature()
            else:
                self.logger.warning("No GPU detected for temperature reading")
                return None
        except Exception as e:
            self.logger.error(f"Error reading GPU temperature: {e}")
            return None

    def _get_nvidia_temperature(self):
        """Get NVIDIA GPU temperature"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                temp_str = result.stdout.strip().split('\n')[0]
                self.gpu_temp = float(temp_str)
                self.logger.debug(f"NVIDIA GPU temperature: {self.gpu_temp}°C")
                return self.gpu_temp
        except Exception as e:
            self.logger.debug(f"Could not read NVIDIA temperature: {e}")
        return None

    def _get_amd_temperature(self):
        """Get AMD GPU temperature"""
        try:
            # Try rocm-smi first
            result = subprocess.run(['rocm-smi', '--showtemp'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'Temperature:' in line:
                        temp_str = line.split(':')[1].strip().replace('°C', '').replace('c', '')
                        self.gpu_temp = float(temp_str)
                        self.logger.debug(f"AMD GPU temperature: {self.gpu_temp}°C")
                        return self.gpu_temp
        except Exception:
            pass

        # Fallback: try sysfs
        try:
            hwmon_paths = glob.glob('/sys/class/hwmon/hwmon*/name')
            for name_file in hwmon_paths:
                with open(name_file, 'r') as f:
                    hwmon_name = f.read().strip()
                    if any(amd_name in hwmon_name.lower() for amd_name in ['amdgpu', 'radeon']):
                        hwmon_dir = os.path.dirname(name_file)
                        temp_files = glob.glob(os.path.join(hwmon_dir, 'temp*_input'))
                        if temp_files:
                            with open(temp_files[0], 'r') as f:
                                temp_millidegrees = int(f.read().strip())
                                self.gpu_temp = temp_millidegrees / 1000.0
                                self.logger.debug(f"AMD GPU temperature from sysfs: {self.gpu_temp}°C")
                                return self.gpu_temp
        except Exception as e:
            self.logger.debug(f"Could not read AMD temperature: {e}")

        return None

    def _get_intel_temperature(self):
        """Get Intel GPU temperature"""
        try:
            # Intel GPUs often share thermal sensors with CPU
            hwmon_paths = glob.glob('/sys/class/hwmon/hwmon*/name')
            for name_file in hwmon_paths:
                with open(name_file, 'r') as f:
                    hwmon_name = f.read().strip()
                    if 'i915' in hwmon_name.lower():
                        hwmon_dir = os.path.dirname(name_file)
                        temp_files = glob.glob(os.path.join(hwmon_dir, 'temp*_input'))
                        if temp_files:
                            with open(temp_files[0], 'r') as f:
                                temp_millidegrees = int(f.read().strip())
                                self.gpu_temp = temp_millidegrees / 1000.0
                                self.logger.debug(f"Intel GPU temperature: {self.gpu_temp}°C")
                                return self.gpu_temp
        except Exception as e:
            self.logger.debug(f"Could not read Intel GPU temperature: {e}")

        return None

    def get_usage_percentage(self):
        """Get GPU usage percentage"""
        try:
            if self.gpu_vendor == "nvidia":
                return self._get_nvidia_usage()
            elif self.gpu_vendor == "amd":
                return self._get_amd_usage()
            elif self.gpu_vendor == "intel":
                return self._get_intel_usage()
            else:
                self.logger.warning("No GPU detected for usage reading")
                return None
        except Exception as e:
            self.logger.error(f"Error reading GPU usage: {e}")
            return None

    def _get_nvidia_usage(self):
        """Get NVIDIA GPU usage percentage"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                usage_str = result.stdout.strip().split('\n')[0]
                self.gpu_usage = float(usage_str)
                self.logger.debug(f"NVIDIA GPU usage: {self.gpu_usage}%")
                return self.gpu_usage
        except Exception as e:
            self.logger.debug(f"Could not read NVIDIA usage: {e}")
        return None

    def _get_amd_usage(self):
        """Get AMD GPU usage percentage"""
        try:
            # Try rocm-smi
            result = subprocess.run(['rocm-smi', '--showuse'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'GPU use (%)' in line:
                        usage_str = line.split(':')[1].strip().replace('%', '')
                        self.gpu_usage = float(usage_str)
                        self.logger.debug(f"AMD GPU usage: {self.gpu_usage}%")
                        return self.gpu_usage
        except Exception as e:
            self.logger.debug(f"Could not read AMD usage: {e}")

        return None

    def _get_intel_usage(self):
        """Get Intel GPU usage percentage"""
        try:
            # Try intel_gpu_top
            result = subprocess.run(['intel_gpu_top', '-J', '-s', '1000'],
                                    capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                # Parse JSON output
                data = json.loads(result.stdout)
                if 'engines' in data:
                    # Calculate average usage across engines
                    total_usage = 0
                    engine_count = 0
                    for engine in data['engines'].values():
                        if 'busy' in engine:
                            total_usage += engine['busy']
                            engine_count += 1

                    if engine_count > 0:
                        self.gpu_usage = total_usage / engine_count
                        self.logger.debug(f"Intel GPU usage: {self.gpu_usage}%")
                        return self.gpu_usage
        except Exception as e:
            self.logger.debug(f"Could not read Intel GPU usage: {e}")

        return None

    def get_frequency(self):
        """Get GPU frequency in MHz"""
        try:
            if self.gpu_vendor == "nvidia":
                return self._get_nvidia_frequency()
            elif self.gpu_vendor == "amd":
                return self._get_amd_frequency()
            elif self.gpu_vendor == "intel":
                return self._get_intel_frequency()
            else:
                self.logger.warning("No GPU detected for frequency reading")
                return None
        except Exception as e:
            self.logger.error(f"Error reading GPU frequency: {e}")
            return None

    def _get_nvidia_frequency(self):
        """Get NVIDIA GPU frequency"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=clocks.current.graphics', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                freq_str = result.stdout.strip().split('\n')[0]
                self.gpu_freq = round(float(freq_str), 2)
                self.logger.debug(f"NVIDIA GPU frequency: {self.gpu_freq} MHz")
                return self.gpu_freq
        except Exception as e:
            self.logger.debug(f"Could not read NVIDIA frequency: {e}")
        return None

    def _get_amd_frequency(self):
        """Get AMD GPU frequency"""
        try:
            # Try rocm-smi
            result = subprocess.run(['rocm-smi', '--showclocks'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'sclk:' in line.lower():
                        freq_str = line.split(':')[1].strip().replace('MHz', '').replace('Mhz', '')
                        self.gpu_freq = round(float(freq_str), 2)
                        self.logger.debug(f"AMD GPU frequency: {self.gpu_freq} MHz")
                        return self.gpu_freq
        except Exception as e:
            self.logger.debug(f"Could not read AMD frequency: {e}")

        return None

    def _get_intel_frequency(self):
        """Get Intel GPU frequency"""
        try:
            # Try to read from sysfs
            freq_files = glob.glob('/sys/class/drm/card*/gt_cur_freq_mhz')
            for freq_file in freq_files:
                try:
                    with open(freq_file, 'r') as f:
                        self.gpu_freq = round(float(f.read().strip()), 2)
                        self.logger.debug(f"Intel GPU frequency: {self.gpu_freq} MHz")
                        return self.gpu_freq
                except (IOError, ValueError):
                    continue
        except Exception as e:
            self.logger.debug(f"Could not read Intel GPU frequency: {e}")

        return None

    def get_all_metrics(self):
        """Get all GPU metrics at once"""
        self.logger.debug("Collecting all GPU metrics")

        if self.gpu_vendor is None:
            self.logger.warning("No GPU detected, returning empty metrics")
            return {
                'vendor': None,
                'name': None,
                'temperature': None,
                'usage_percentage': None,
                'frequency': None
            }

        metrics = {
            'vendor': self.gpu_vendor,
            'name': self.gpu_name,
            'temperature': self.get_temperature(),
            'usage_percentage': self.get_usage_percentage(),
            'frequency': self.get_frequency()
        }

        # Log summary of collected metrics
        temp_str = f"{metrics['temperature']:.1f}°C" if metrics['temperature'] is not None else "N/A"
        usage_str = f"{metrics['usage_percentage']:.1f}%" if metrics['usage_percentage'] is not None else "N/A"
        freq_str = f"{metrics['frequency']:.0f} MHz" if metrics['frequency'] is not None else "N/A"

        self.logger.debug(f"GPU metrics collected - Vendor: {metrics['vendor']}, "
                          f"Temp: {temp_str}, Usage: {usage_str}, Freq: {freq_str}")

        return metrics

    def get_metric_value(self, metric_name) -> str:
        if metric_name == "gpu_temperature":
            temperature = self.get_temperature()
            return f'{temperature}' if temperature is not None else 'N/A'
        if metric_name == "gpu_usage":
            percentage = self.get_usage_percentage()
            return f'{percentage}' if percentage is not None else 'N/A'
        if metric_name == "gpu_frequency":
            frequency = self.get_frequency()
            return f'{frequency}' if frequency is not None else 'N/A'
        return 'N/A'

    def __str__(self):
        """String representation of GPU metrics"""
        if self.gpu_vendor is None:
            return "GPU - No supported GPU detected"

        temp = self.get_temperature()
        usage = self.get_usage_percentage()
        freq = self.get_frequency()

        temp_str = f"{temp:.1f}°C" if temp is not None else "N/A"
        usage_str = f"{usage:.1f}%" if usage is not None else "N/A"
        freq_str = f"{freq:.0f} MHz" if freq is not None else "N/A"

        return (f"GPU ({self.gpu_name}) - Usage: {usage_str}, "
                f"Temperature: {temp_str}, Frequency: {freq_str}")
