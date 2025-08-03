# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import glob
import os

import psutil

from . import Metrics
from ...common.logging_config import LoggerConfig


class CpuMetrics(Metrics):
    def __init__(self):
        super().__init__()
        self.logger = LoggerConfig.setup_service_logger()
        self.cpu_usage = 0.0
        self.cpu_temp = 0.0
        self.cpu_freq = 0.0
        self.logger.debug("CpuMetrics initialized")

    def get_temperature(self):
        """
        Get the processor temperature in Celsius.
        Returns the temperature or None if not available.
        """
        try:
            # Try first with psutil
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()

                # Search in temperature sensors
                for name, entries in temps.items():
                    if any(keyword in name.lower() for keyword in ['cpu', 'core', 'package']):
                        for entry in entries:
                            if entry.current:
                                self.cpu_temp = entry.current
                                self.logger.debug(f"Temperature read from psutil sensor '{name}': {self.cpu_temp}°C")
                                return self.cpu_temp

            # Fallback: read directly from /sys/class/thermal
            thermal_zones = glob.glob('/sys/class/thermal/thermal_zone*/type')
            for zone_type_file in thermal_zones:
                zone_dir = os.path.dirname(zone_type_file)

                try:
                    with open(zone_type_file, 'r') as f:
                        zone_type = f.read().strip()

                    # Search for CPU-related zones
                    if any(keyword in zone_type.lower() for keyword in ['cpu', 'x86_pkg_temp', 'coretemp']):
                        temp_file = os.path.join(zone_dir, 'temp')
                        if os.path.exists(temp_file):
                            with open(temp_file, 'r') as f:
                                temp_millidegrees = int(f.read().strip())
                                self.cpu_temp = temp_millidegrees / 1000.0
                                self.logger.debug(
                                    f"Temperature read from thermal zone '{zone_type}': {self.cpu_temp}°C")
                                return self.cpu_temp
                except (IOError, ValueError) as e:
                    self.logger.debug(f"Failed to read thermal zone {zone_type_file}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error reading temperature: {e}")

        self.logger.warning("Could not read CPU temperature from any source")
        return None

    def get_usage_percentage(self):
        """
        Get the processor usage percentage.
        Returns a float between 0.0 and 100.0.
        """
        try:
            # Use psutil to get average CPU usage
            self.cpu_usage = psutil.cpu_percent(interval=1)
            self.logger.debug(f"CPU usage: {self.cpu_usage}%")
            return self.cpu_usage
        except Exception as e:
            self.logger.error(f"Error reading CPU usage: {e}")
            return 0.0

    def get_frequency(self):
        """
        Get the current processor frequency in MHz.
        Returns the frequency or None if not available.
        """
        try:
            # Use psutil to get CPU frequencies
            freq_info = psutil.cpu_freq()
            if freq_info:
                self.cpu_freq = round(freq_info.current, 2)
                self.logger.debug(f"CPU frequency from psutil: {self.cpu_freq} MHz")
                return self.cpu_freq

            # Fallback: read from /proc/cpuinfo
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('cpu MHz'):
                        freq_str = line.split(':')[1].strip()
                        self.cpu_freq = round(float(freq_str))
                        self.logger.debug(f"CPU frequency from /proc/cpuinfo: {self.cpu_freq} MHz")
                        return self.cpu_freq

        except Exception as e:
            self.logger.error(f"Error reading CPU frequency: {e}")

        self.logger.warning("Could not read CPU frequency from any source")
        return None

    def get_all_metrics(self):
        """
        Get all CPU metrics at once.
        Returns a dictionary with the metrics.
        """
        self.logger.debug("Collecting all CPU metrics")

        metrics = {
            'temperature': self.get_temperature(),
            'usage_percentage': self.get_usage_percentage(),
            'frequency': self.get_frequency()
        }

        # Log summary of collected metrics
        temp_str = f"{metrics['temperature']:.1f}°C" if metrics['temperature'] is not None else "N/A"
        usage_str = f"{metrics['usage_percentage']:.1f}%" if metrics['usage_percentage'] is not None else "N/A"
        freq_str = f"{metrics['frequency']:.0f} MHz" if metrics['frequency'] is not None else "N/A"

        self.logger.debug(f"Metrics collected - Temp: {temp_str}, Usage: {usage_str}, Freq: {freq_str}")

        return metrics

    def get_metric_value(self, metric_name) -> str:
        if metric_name == "cpu_temperature":
            temperature = self.get_temperature()
            return f'{temperature}' if temperature is not None else 'N/A'
        if metric_name == "cpu_usage":
            percentage = self.get_usage_percentage()
            return f'{percentage}' if percentage is not None else 'N/A'
        if metric_name == "cpu_frequency":
            frequency = self.get_frequency()
            return f'{frequency}' if frequency is not None else 'N/A'
        return 'N/A'

    def __str__(self):
        """
        String representation of CPU metrics.
        """
        temp = self.get_temperature()
        usage = self.get_usage_percentage()
        freq = self.get_frequency()

        temp_str = f"{temp:.1f}°C" if temp is not None else "N/A"
        usage_str = f"{usage:.1f}%" if usage is not None else "N/A"
        freq_str = f"{freq:.0f} MHz" if freq is not None else "N/A"

        return f"CPU - Usage: {usage_str}, Temperature: {temp_str}, Frequency: {freq_str}"
