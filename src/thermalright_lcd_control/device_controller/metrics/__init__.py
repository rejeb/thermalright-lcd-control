# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb


from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Metrics(ABC):
    """
    Abstract base class for all system metrics.
    This class defines the common interface that must be implemented
    by specialized metrics classes (CPU, GPU, etc.).
    """

    def __init__(self):
        """Initialize the base metrics class."""
        pass

    @abstractmethod
    def get_temperature(self) -> Optional[float]:
        """
        Get temperature in degrees Celsius.

        Returns:
            Optional[float]: Temperature in °C or None if not available.
        """
        pass

    @abstractmethod
    def get_usage_percentage(self) -> Optional[float]:
        """
        Get usage percentage.

        Returns:
            Optional[float]: Usage percentage (0.0-100.0) or None if not available.
        """
        pass

    @abstractmethod
    def get_frequency(self) -> Optional[float]:
        """
        Get frequency in MHz.

        Returns:
            Optional[float]: Frequency in MHz or None if not available.
        """
        pass

    @abstractmethod
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics at once.

        Returns:
            Dict[str, Any]: Dictionary containing all metrics.
        """
        pass

    @abstractmethod
    def get_metric_value(self, metric_name) -> Any:
        pass

    @abstractmethod
    def __str__(self) -> str:
        """
        Text representation of metrics.

        Returns:
            str: Text description of metrics.
        """
        pass
