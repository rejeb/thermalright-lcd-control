# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Controls manager for UI composition controls"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
                               QGroupBox, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QCheckBox, QApplication)
from PySide6.QtWidgets import QSlider

from ..widgets.draggable_widget import TextStyleConfig


class ControlsManager:
    """Manages all UI controls for composition"""

    def __init__(self, parent, text_style: TextStyleConfig, metric_widgets: dict):
        self.parent = parent
        self.text_style = text_style
        self.metric_widgets = metric_widgets

        # Control widgets
        self.opacity_input = None
        self.opacity_value_label = None
        self.font_size_spin = None
        self.color_btn = None
        self.show_date_checkbox = None
        self.show_time_checkbox = None
        self.metric_checkboxes = {}
        self.metric_label_inputs = {}
        self.metric_unit_inputs = {}

    def create_controls_widget(self) -> QScrollArea:
        """Create and return the controls widget"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)

        # Add all control sections
        controls_layout.addWidget(self._create_opacity_controls())
        controls_layout.addWidget(self._create_text_style_controls())
        controls_layout.addWidget(self._create_overlay_controls())
        controls_layout.addWidget(self._create_action_controls())

        scroll_area.setWidget(controls_container)
        return scroll_area

    def _create_opacity_controls(self) -> QGroupBox:
        """Create foreground opacity controls"""
        opacity_group = QGroupBox()
        opacity_layout = QVBoxLayout(opacity_group)  # Changé en VBoxLayout

        # Layout horizontal pour le label et la valeur
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("Opacity:"))
        label_layout.addStretch()  # Pousse la valeur vers la droite

        self.opacity_value_label = QLabel("50%")
        label_layout.addWidget(self.opacity_value_label)

        # Slider qui prend toute la largeur
        self.opacity_input = QSlider(Qt.Horizontal)
        self.opacity_input.setRange(0, 100)
        self.opacity_input.setValue(50)
        self.opacity_input.setTickPosition(QSlider.TicksBelow)
        self.opacity_input.setTickInterval(10)

        self.opacity_input.valueChanged.connect(self._on_opacity_slider_changed)
        self.opacity_input.sliderReleased.connect(self.parent.on_opacity_editing_finished)

        # Ajouter les layouts
        opacity_layout.addLayout(label_layout)
        opacity_layout.addWidget(self.opacity_input)

        return opacity_group



    def _on_opacity_slider_changed(self, value):
        """Handle slider value change"""
        self.opacity_value_label.setText(f"{value}%")
        self.parent.on_opacity_text_changed(str(value))


    def _create_text_style_controls(self) -> QGroupBox:
        """Create text style controls"""
        style_group = QGroupBox("Text Style")
        style_layout = QHBoxLayout(style_group)

        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(self.text_style.font_size)
        self.font_size_spin.valueChanged.connect(self.parent.on_font_size_changed)

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Size:"))
        font_layout.addWidget(self.font_size_spin)
        font_layout.addStretch(1)

        # Color
        color_layout = QHBoxLayout()
        self.color_btn = QPushButton()
        self.color_btn.clicked.connect(self.parent.choose_color)
        self.update_color_button()

        color_layout.addWidget(QLabel("Choose Colors:"))
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch(1)

        style_layout.addLayout(font_layout)
        style_layout.addLayout(color_layout)

        return style_group

    def _create_overlay_controls(self) -> QGroupBox:
        """Create overlay widget controls"""
        overlay_group = QGroupBox("Overlay Widgets")
        overlay_layout = QVBoxLayout(overlay_group)

        # Date/Time controls
        datetime_layout = QHBoxLayout()
        self.show_date_checkbox = QCheckBox("Show Date")
        self.show_date_checkbox.setChecked(True)
        self.show_date_checkbox.toggled.connect(self.parent.on_show_date_changed)

        self.show_time_checkbox = QCheckBox("Show Time")
        self.show_time_checkbox.setChecked(False)
        self.show_time_checkbox.toggled.connect(self.parent.on_show_time_changed)

        datetime_layout.addWidget(self.show_date_checkbox)
        datetime_layout.addWidget(self.show_time_checkbox)
        overlay_layout.addLayout(datetime_layout)

        # Metric controls
        cpu_metrics_layout = QHBoxLayout()
        cpu_metrics_layout.addWidget(QLabel("CPU Metrics:"))
        gpu_metrics_layout = QHBoxLayout()
        gpu_metrics_layout.addWidget(QLabel("GPU Metrics:"))

        cpu_metric_labels = {
            "cpu_temperature": "Temp",
            "cpu_usage": "Usage",
            "cpu_frequency": "Frequency"
        }

        gpu_metric_labels = {
            "gpu_temperature": "Temp",
            "gpu_usage": "Usage",
            "gpu_frequency": "Frequency"
        }

        for metric_name, display_name in cpu_metric_labels.items():
            metric_layout = self._create_metric_layout(display_name, metric_name)
            cpu_metrics_layout.addLayout(metric_layout)

        for metric_name, display_name in gpu_metric_labels.items():
            metric_layout = self._create_metric_layout(display_name, metric_name)
            gpu_metrics_layout.addLayout(metric_layout)

        overlay_layout.addLayout(cpu_metrics_layout)
        overlay_layout.addLayout(gpu_metrics_layout)
        return overlay_group

    def _create_metric_layout(self, display_name, metric_name):
        metric_layout = QHBoxLayout()
        # Checkbox
        checkbox = QCheckBox(display_name)
        checkbox.setChecked(False)
        checkbox.setStyleSheet(self._get_smart_checkbox_style())
        checkbox.toggled.connect(lambda checked, name=metric_name: self.parent.on_metric_toggled(name, checked))
        self.metric_checkboxes[metric_name] = checkbox
        metric_layout.addWidget(checkbox)
        # Label input
        metric_layout.addWidget(QLabel("Label:"))
        label_input = QLineEdit()
        label_input.setPlaceholderText(self.metric_widgets[metric_name]._get_default_label())
        label_input.textChanged.connect(
            lambda text, name=metric_name: self.parent.on_metric_label_changed(name, text))
        label_input.setMaximumWidth(60)
        self.metric_label_inputs[metric_name] = label_input
        metric_layout.addWidget(label_input)
        # Unit input
        metric_layout.addWidget(QLabel("Unit:"))
        unit_input = QLineEdit()
        unit_input.setPlaceholderText(self.metric_widgets[metric_name]._get_default_unit())
        unit_input.textChanged.connect(
            lambda text, name=metric_name: self.parent.on_metric_unit_changed(name, text))
        unit_input.setMaximumWidth(40)
        self.metric_unit_inputs[metric_name] = unit_input
        metric_layout.addWidget(unit_input)
        metric_layout.addStretch()
        return metric_layout

    def _create_action_controls(self) -> QGroupBox:
        """Create action buttons"""
        actions_group = QGroupBox()
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.addStretch()
        actions_layout.setSpacing(10)
        save_config_btn = QPushButton("Save")
        save_config_btn.clicked.connect(self.parent.generate_config_yaml)
        save_config_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; 
                         padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        save_config_btn.setFixedSize(100, 35)

        preview_config_btn = QPushButton("Apply")
        preview_config_btn.clicked.connect(self.parent.generate_preview)
        preview_config_btn.setStyleSheet("""
                QPushButton { background-color: #4CAF50; color: white; font-weight: bold; 
                             padding: 8px; border-radius: 4px; }
                QPushButton:hover { background-color: #45a049; }
            """)
        preview_config_btn.setFixedSize(100, 35)

        actions_layout.addWidget(save_config_btn, alignment=Qt.AlignmentFlag.AlignRight)
        actions_layout.addWidget(preview_config_btn, alignment=Qt.AlignmentFlag.AlignRight)

        return actions_group

    def update_color_button(self):
        """Update color button appearance"""
        self.color_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.text_style.color.name()}; border: 1px solid #666; 
                          padding: 5px; color: {'black' if self.text_style.color.lightness() > 128 else 'white'}; }}
        """)

    def _get_smart_checkbox_style(self):
        """Style intelligent qui détecte automatiquement le thème"""
        # Détecter si on est en mode sombre
        palette = QApplication.instance().palette()
        is_dark = palette.color(QPalette.ColorRole.Window).lightness() < 128

        if is_dark:
            return """
            QCheckBox {
                color: #ffffff;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #666666;
                border-radius: 3px;
                background-color: #2b2b2b;
            }
            QCheckBox::indicator:hover {
                border-color: #0078d4;
                background-color: #3c3c3c;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            """
        else:
            return """
            QCheckBox {
                color: #000000;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #999999;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:hover {
                border-color: #0078d4;
                background-color: #f0f0f0;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            """
