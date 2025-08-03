# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Main window for Media Preview application"""
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtGui import QMouseEvent, QColor
from PySide6.QtWidgets import (QLabel)

from ...device_controller.display.utils import _get_default_font_name
from ...device_controller.metrics.cpu_metrics import CpuMetrics
from ...device_controller.metrics.gpu_metrics import GpuMetrics


class TextStyleConfig:
    """Global text style configuration"""

    def __init__(self):
        self.font_family = _get_default_font_name()
        self.font_size = 18
        self.color = QColor(0, 0, 0)
        self.bold = True

    def selected_stylesheet(self):
        """Convert to CSS stylesheet for selected widget"""
        return f"""
            background-color: transparent; color: {self.color.name()};
            border: 0px transparent; padding: 0px;
            font-family: {self.font_family}; font-size: {self.font_size}px;
            font-weight: {'bold' if self.bold else 'normal'};
        """

    def hidden_stylesheet(self):
        return f"""
                background-color: transparent; color: {self.color.name()};
                border: 0px transparent; padding: 0px;
                font-family: {self.font_family}; font-size: {self.font_size}px;
                font-weight: {'bold' if self.bold else 'normal'};
            """


class DraggableWidget(QLabel):
    """Base class for draggable overlay widgets"""
    positionChanged = Signal(QPoint)

    def __init__(self, parent=None, text="", widget_name="widget"):
        super().__init__(parent)
        self.widget_name = widget_name
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.dragging = False
        self.drag_start_position = QPoint()
        self.setText(text)
        self.adjustSize()
        self.move(10, 10)
        self.text_style = TextStyleConfig()
        self.enabled = False
        self.display_text = ""
        self.update_display()

    def update_display(self):
        """Update display"""
        if self.enabled:
            self.setText(self.display_text)
            self.setStyleSheet(f"QLabel {{ {self.text_style.selected_stylesheet()} }}")
            self.setDisabled(False)
        else:
            self.setText("")
            self.setStyleSheet(f"QLabel {{ {self.text_style.hidden_stylesheet()} }}")
            self.setDisabled(True)
        self.adjustSize()

    def apply_style(self, style_config: TextStyleConfig):
        self.text_style = style_config
        self.update_display()

    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start_position = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle dragging movement"""
        if self.dragging and event.buttons() == Qt.LeftButton:
            new_pos = self.pos() + event.pos() - self.drag_start_position
            if self.parent():
                parent_rect = self.parent().rect()
                widget_rect = self.rect()
                new_pos.setX(max(0, min(new_pos.x(), parent_rect.width() - widget_rect.width())))
                new_pos.setY(max(0, min(new_pos.y(), parent_rect.height() - widget_rect.height())))
            self.move(new_pos)
            self.positionChanged.emit(new_pos)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Finish dragging"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(Qt.ArrowCursor)

    def enterEvent(self, event):
        """Change cursor on hover"""
        self.setCursor(Qt.OpenHandCursor)

    def leaveEvent(self, event):
        """Reset cursor"""
        if not self.dragging:
            self.setCursor(Qt.ArrowCursor)

    def set_enabled(self, enabled):
        """Enable/disable display"""
        self.enabled = enabled
        self.update_display()


class TimerWidget(DraggableWidget):
    """Base class for time-based widgets"""

    def __init__(self, parent=None, widget_name="", time_format=""):
        super().__init__(parent, "", widget_name)
        self.time_format = time_format
        self.display_text = datetime.now().strftime(self.time_format)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)


class DateWidget(TimerWidget):
    """Date display widget"""

    def __init__(self, parent=None):
        super().__init__(parent, "date", "%d/%m")


class TimeWidget(TimerWidget):
    """Time display widget"""

    def __init__(self, parent=None):
        super().__init__(parent, "time", "%H:%M")


class MetricWidget(DraggableWidget):
    """Generic metric display widget"""

    def __init__(self, metric: type[CpuMetrics | GpuMetrics], parent=None, metric_name="", display_text=""):
        super().__init__(parent, display_text, metric_name)
        self.metric_instance = metric
        self.metric_name = metric_name
        self.enabled = False
        self.custom_label = ""
        self.custom_unit = ""
        self.format = "{label}{value}{unit}"
        self.display_text = self.format.format(
            label=self.format_label(), value=self.get_value(), unit=self.get_unit()
        )
        self.setText(self.display_text)
        self._set_initial_position()
        self.update_display()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

    def _set_initial_position(self):
        """Set initial position based on widget type"""
        positions = {
            "cpu_temperature": (10, 40), "gpu_temperature": (10, 70), "cpu_usage": (10, 100),
            "gpu_usage": (10, 130), "cpu_frequency": (10, 160), "gpu_frequency": (10, 190)
        }
        if self.metric_name in positions:
            self.move(*positions[self.metric_name])

    def _set_initial_position(self):
        """Set initial position based on widget type"""
        positions = {
            "cpu_temperature": (10, 40), "gpu_temperature": (10, 70), "cpu_usage": (10, 100),
            "gpu_usage": (10, 130), "cpu_frequency": (10, 160), "gpu_frequency": (10, 190)
        }
        if self.metric_name in positions:
            self.move(*positions[self.metric_name])

    def set_custom_label(self, label):
        """Définir un label personnalisé"""
        self.custom_label = label
        self.display_text = self.format.format(
            label=self.format_label(), value=self.get_value(), unit=self.get_unit()
        )
        self.setText(self.display_text)
        self.update_display()

    def set_custom_unit(self, unit):
        """Définir une unité personnalisée"""
        self.custom_unit = unit
        self.display_text = self.format.format(
            label=self.format_label(), value=self.get_value(), unit=self.get_unit()
        )
        self.setText(self.display_text)
        self.update_display()

    def format_label(self):
        return f"{self.custom_label}: " if self.custom_label else ""

    def get_label(self):
        """Obtenir le label (personnalisé ou par défaut)"""
        return self.custom_label if self.custom_label else ""

    def get_unit(self):
        """Obtenir l'unité (personnalisée ou par défaut)"""
        return self.custom_unit if self.custom_unit else ""

    def get_value(self):
        value = self.metric_instance.get_metric_value(self.metric_name)
        return value if value is not None else "N/A"

    def _get_default_label(self):
        """Obtenir le label par défaut basé sur le metric_name"""
        defaults = {
            "cpu_temperature": "CPU",
            "gpu_temperature": "GPU",
            "cpu_usage": "CPU%",
            "gpu_usage": "GPU%",
            "cpu_frequency": "CPU",
            "gpu_frequency": "GPU"
        }
        return defaults.get(self.metric_name, "")

    def _get_default_unit(self):
        """Obtenir l'unité par défaut basée sur le metric_name"""
        defaults = {
            "cpu_temperature": "°",
            "gpu_temperature": "°",
            "cpu_usage": "%",
            "gpu_usage": "%",
            "cpu_frequency": "MHZ",
            "gpu_frequency": "MHZ"
        }
        return defaults.get(self.metric_name, "")
