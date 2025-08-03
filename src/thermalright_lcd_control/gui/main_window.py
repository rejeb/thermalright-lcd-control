# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Main window for Media Preview application"""

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtWidgets import (QTabWidget, QFrame, QColorDialog, QMessageBox)

from .components.config_generator import ConfigGenerator
from .components.controls_manager import ControlsManager
from .components.preview_manager import PreviewManager
from .tabs.media_tab import MediaTab
from .tabs.themes_tab import ThemesTab
from .utils.config_loader import load_config
from .widgets.draggable_widget import *
from ..common.logging_config import get_gui_logger
from ..device_controller.metrics.cpu_metrics import CpuMetrics
from ..device_controller.metrics.gpu_metrics import GpuMetrics


class MediaPreviewUI(QMainWindow):

    def __init__(self, config_file_path=None, detected_device: dict = None):
        super().__init__()
        self.logger = get_gui_logger()
        # Initialize configuration and device
        self.config = load_config(config_file_path)
        self.cpu_metric = CpuMetrics()
        self.gpu_metric = GpuMetrics()
        title_info = (f"{hex(detected_device['vid'])}-{hex(detected_device['pid'])} | "
                      f"{detected_device['width']}x{detected_device['height']}")

        self.setWindowTitle(f"ThermalRight LCD Control:  {title_info}")

        self.detected_device = detected_device
        preview_width = detected_device['width'] if detected_device else 320
        preview_height = detected_device['height'] if detected_device else 240

        # Initialize paths
        paths = self.config.get('paths', {})
        self.backgrounds_dir = paths.get('backgrounds_dir', './themes/backgrounds')
        self.foregrounds_dir = paths.get('foregrounds_dir', './themes/foregrounds')

        # Initialize components
        self.text_style = TextStyleConfig()
        self.media_tabs = []

        # UI Components will be initialized in setup_ui
        self.preview_label = None
        self.preview_manager = None
        self.controls_manager = None
        self.config_generator = ConfigGenerator(self.config)

        # Initialize UI
        self.setup_window(preview_width, preview_height)
        self.setup_ui()

    def setup_window(self, preview_width: int, preview_height: int):
        """Configure window size and properties"""
        window_config = self.config.get('window', {})
        default_width = window_config.get('default_width', 1200)
        default_height = window_config.get('default_height', 600)

        min_width = max(window_config.get('min_width', 800), preview_width + 580)
        min_height = max(window_config.get('min_height', 600), preview_height + 200)

        self.setGeometry(100, 100, max(default_width, min_width), max(default_height, min_height))
        self.setMinimumSize(min_width, min_height)

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Left side (preview + controls)
        left_widget = QWidget()
        preview_width = self.detected_device['width'] if self.detected_device else 320
        left_widget.setMinimumWidth(max(350, preview_width + 20))
        left_layout = QHBoxLayout(left_widget)

        # Preview area
        self.setup_preview_area(left_layout)

        # Create overlay widgets first
        self.create_overlay_widgets()

        # Controls (now that metric_widgets exists)
        self.controls_manager = ControlsManager(self, self.text_style, self.metric_widgets)
        left_layout.addWidget(self.controls_manager.create_controls_widget(), 6)

        # Right side (tabs)
        right_widget = QWidget()
        right_widget.setMinimumWidth(500)
        right_layout = QVBoxLayout(right_widget)
        self.setup_tabs_area(right_layout)

        main_layout.addWidget(left_widget, 4)
        main_layout.addWidget(right_widget, 6)
        self.themes_tab.auto_load_first_theme()

    def setup_preview_area(self, parent_layout):
        """Configure preview area with device-specific size and centered"""
        center_layout = QHBoxLayout()
        center_layout.addStretch(1)

        # Get dimensions
        preview_width = self.detected_device['width'] if self.detected_device else 320
        preview_height = self.detected_device['height'] if self.detected_device else 240

        # Preview frame
        frame_width, frame_height = preview_width + 4, preview_height + 4
        preview_frame = QFrame()
        preview_frame.setFixedSize(frame_width, frame_height)
        preview_frame.setStyleSheet("QFrame { border: 2px solid #ccc; background-color: white; }")

        # Preview widget and label
        self.preview_widget = QWidget(preview_frame)
        self.preview_widget.setGeometry(2, 2, preview_width, preview_height)
        self.preview_widget.setStyleSheet("background-color: white;")

        self.preview_label = QLabel(self.preview_widget)
        self.preview_label.setGeometry(0, 0, preview_width, preview_height)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(
            "QLabel { background-color: white; color: #333; border: none; font-size: 12px; }")
        self.preview_label.setText("Initializing preview...")

        # Initialize preview manager with actual components
        self.preview_manager = PreviewManager(self.config, self.preview_label, self.text_style)
        self.preview_manager.set_device_dimensions(preview_width, preview_height)

        center_layout.addWidget(preview_frame)
        center_layout.addStretch(1)
        parent_layout.addLayout(center_layout, 4)

    def create_overlay_widgets(self):
        """Create all overlay widgets"""
        # Date widget
        self.date_widget = DateWidget(self.preview_widget)
        self.date_widget.move(200, 10)
        self.date_widget.apply_style(self.text_style)
        self.date_widget.set_enabled(True)

        # Time widget
        self.time_widget = TimeWidget(self.preview_widget)
        self.time_widget.move(200, 40)
        self.time_widget.apply_style(self.text_style)
        self.time_widget.set_enabled(False)

        # Metric widgets
        metrics_config = [
            "cpu_temperature", "gpu_temperature",
            "cpu_usage", "gpu_usage",
            "cpu_frequency", "gpu_frequency"
        ]

        self.metric_widgets = {}
        for metric_name in metrics_config:
            metric = self.cpu_metric if metric_name.startswith("cpu_") else self.gpu_metric
            widget = MetricWidget(metric=metric, parent=self.preview_widget, metric_name=metric_name)
            widget.apply_style(self.text_style)
            widget.set_enabled(False)
            self.metric_widgets[metric_name] = widget

    def apply_style_to_all_widgets(self):
        """Apply current text style to all overlay widgets"""
        for widget in [self.date_widget, self.time_widget] + list(self.metric_widgets.values()):
            if widget:
                widget.apply_style(self.text_style)

    def setup_tabs_area(self, parent_layout):
        """Configure tabs area for media files"""
        self.tab_widget = QTabWidget()

        # Themes tab (moved to first position)
        self.themes_tab = ThemesTab(self.config)
        self.themes_tab.theme_selected.connect(self.on_theme_selected)
        self.media_tabs.append(self.themes_tab)
        self.tab_widget.addTab(self.themes_tab, "Themes")

        # Media tabs (Backgrounds and Foregrounds)
        for tab_name, media_dir, callback in [("Backgrounds", self.backgrounds_dir, self.on_background_clicked),
                                              ("Foregrounds", self.foregrounds_dir, self.on_foreground_clicked)]:
            tab = MediaTab(media_dir=media_dir, config=self.config, tab_name=tab_name)
            tab.thumbnail_clicked.connect(callback)
            if tab_name == "Backgrounds":
                tab.collection_created.connect(self.on_collection_created)

            self.media_tabs.append(tab)
            self.tab_widget.addTab(tab, tab_name)

        parent_layout.addWidget(self.tab_widget)

    def on_theme_selected(self, theme_path: str):
        """Handle theme selection"""
        self.logger.debug(f"on_theme_selected called with: {theme_path}")
        try:
            import yaml
            from pathlib import Path
            from PySide6.QtGui import QColor

            # Load theme configuration
            with open(theme_path, 'r', encoding='utf-8') as f:
                theme_config = yaml.safe_load(f)

            display_config = theme_config.get('display', {})
            self.logger.debug(f"Display config loaded: {display_config.keys()}")

            # Load background
            background_config = display_config.get('background', {})
            self.logger.debug(f"Background config: {background_config}")
            background_path = background_config.get('path')
            self.logger.debug(f"Background path: {background_path}")
            self.logger.debug(f"Preview manager exists: {self.preview_manager is not None}")

            if background_path and self.preview_manager:
                self.logger.debug(f"Setting background: {background_path}")
                self.preview_manager.set_background(background_path)
            else:
                if not background_path:
                    self.logger.debug("Background path is empty or None")
                if not self.preview_manager:
                    self.logger.debug("Preview manager is None")

            # Load foreground if enabled
            foreground_config = display_config.get('foreground', {})
            if foreground_config.get('enabled', False):
                foreground_path = foreground_config.get('path')
                foreground_alpha = foreground_config.get('alpha', 1.0)
                self.logger.debug(f"Foreground path: {foreground_path}, alpha: {foreground_alpha}")

                if foreground_path and self.preview_manager:
                    self.preview_manager.set_foreground(foreground_path)
                    self.preview_manager.set_foreground_opacity(foreground_alpha)

                    # Update opacity controls
                    if self.controls_manager:
                        opacity_percentage = int(foreground_alpha * 100)
                        self.controls_manager.opacity_input.setValue(opacity_percentage)

            # Apply date widget configuration
            date_config = display_config.get('date', {})
            if date_config and self.date_widget:
                self.apply_widget_config(self.date_widget, date_config)

            # Apply time widget configuration
            time_config = display_config.get('time', {})
            if time_config and self.time_widget:
                self.apply_widget_config(self.time_widget, time_config)

            # Apply metrics configurations
            metrics_config = display_config.get('metrics', {})
            if metrics_config and 'configs' in metrics_config:
                self.apply_metrics_config(metrics_config['configs'])

            # Update controls to reflect current widget states
            self.update_controls_from_widgets()

            self.logger.debug(f"Theme loaded: {Path(theme_path).name}")

        except Exception as e:
            self.logger.error(f"Exception in on_theme_selected: {e}")
            QMessageBox.warning(self, "Theme Load Error", f"Failed to load theme:\n{str(e)}")

    def apply_widget_config(self, widget, config):
        """Apply configuration to a date/time widget"""
        try:
            # Apply enabled state
            enabled = config.get('enabled', False)
            widget.set_enabled(enabled)

            # Apply position
            position = config.get('position', {})
            if position:
                x = position.get('x', widget.pos().x())
                y = position.get('y', widget.pos().y())
                widget.move(x, y)

            # Apply font size
            font_size = config.get('font_size')
            if font_size:
                self.text_style.font_size = font_size

            # Apply color
            color_hex = config.get('color')
            if color_hex:
                color = self.hex_to_qcolor(color_hex)
                if color:
                    self.text_style.color = color

            # Apply style to widget
            widget.apply_style(self.text_style)

        except Exception as e:
            self.logger.error(f"Error applying widget config: {e}")

    def apply_metrics_config(self, metrics_configs):
        """Apply configurations to metric widgets"""
        try:
            # First disable all metrics
            for metric_widget in self.metric_widgets.values():
                metric_widget.set_enabled(False)

            # Apply configuration for each metric
            for metric_config in metrics_configs:
                metric_name = metric_config.get('name')
                if metric_name not in self.metric_widgets:
                    continue

                widget = self.metric_widgets[metric_name]

                # Apply enabled state
                enabled = metric_config.get('enabled', False)
                widget.set_enabled(enabled)

                # Apply position
                position = metric_config.get('position', {})
                if position:
                    x = position.get('x', widget.pos().x())
                    y = position.get('y', widget.pos().y())
                    widget.move(x, y)

                # Apply custom label and unit
                label = metric_config.get('label', '')
                self.logger.debug(f"metric: {metric_name} Label: {label}")
                unit = metric_config.get('unit', '')
                if label:
                    widget.set_custom_label(label)
                if unit:
                    widget.set_custom_unit(unit)

                # Apply font size and color (create a temporary style for this metric)
                font_size = metric_config.get('font_size')
                color_hex = metric_config.get('color')

                if font_size or color_hex:
                    # Create a copy of the current text style for this metric
                    metric_style = TextStyleConfig()
                    metric_style.font_size = font_size if font_size else self.text_style.font_size

                    if color_hex:
                        color = self.hex_to_qcolor(color_hex)
                        metric_style.color = color if color else self.text_style.color
                    else:
                        metric_style.color = self.text_style.color

                    widget.apply_style(metric_style)
                else:
                    widget.apply_style(self.text_style)

                # Update widget display
                widget.update_display()

        except Exception as e:
            self.logger.error(f"Error applying metrics config: {e}")

    def update_controls_from_widgets(self):
        """Update control interface to reflect current widget states"""
        try:
            if not self.controls_manager:
                return

            # Update date checkbox
            if hasattr(self.controls_manager, 'show_date_checkbox'):
                self.controls_manager.show_date_checkbox.setChecked(
                    self.date_widget.enabled if self.date_widget else False)

            # Update time checkbox
            if hasattr(self.controls_manager, 'show_time_checkbox'):
                self.controls_manager.show_time_checkbox.setChecked(
                    self.time_widget.enabled if self.time_widget else False)

            for metric_name, widget in self.metric_widgets.items():
                # Update checkbox
                if hasattr(self.controls_manager, 'metric_checkboxes'):
                    checkbox = self.controls_manager.metric_checkboxes[metric_name]
                    checkbox.setChecked(widget.enabled)

                if hasattr(self.controls_manager, 'metric_unit_inputs') and widget.enabled:
                    label_input = self.controls_manager.metric_label_inputs[metric_name]
                    label_input.setText(widget.get_label())

                # Update unit input
                if hasattr(self.controls_manager, 'metric_unit_inputs') and widget.enabled:
                    unit_input = self.controls_manager.metric_unit_inputs[metric_name]
                    unit_input.setText(widget.get_unit())

            # Update font size control
            if hasattr(self.controls_manager, 'font_size_spin'):
                self.controls_manager.font_size_spin.setValue(self.text_style.font_size)

            # Update color button
            if hasattr(self.controls_manager, 'update_color_button'):
                self.controls_manager.update_color_button()

        except Exception as e:
            self.logger.error(f"Error updating controls from widgets: {e}")

    def hex_to_qcolor(self, hex_color: str) -> QColor:
        """Convert hex color string to QColor"""
        try:
            # Remove # if present
            hex_color = hex_color.lstrip('#')

            # Handle different hex formats
            if len(hex_color) == 6:  # RGB
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return QColor(r, g, b)
            elif len(hex_color) == 8:  # RGBA
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                a = int(hex_color[6:8], 16)
                return QColor(r, g, b, a)
            else:
                self.logger.error(f"Invalid hex color format: {hex_color}")
                return None

        except ValueError as e:
            self.logger.error(f"Error parsing hex color {hex_color}: {e}")
            return None

    # Event handlers
    def choose_color(self):
        """Open color chooser dialog"""
        color = QColorDialog.getColor(self.text_style.color, self)
        if color.isValid():
            self.text_style.color = color
            self.controls_manager.update_color_button()
            self.apply_style_to_all_widgets()

    def on_font_size_changed(self, size):
        """Handle font size change"""
        self.text_style.font_size = size
        self.apply_style_to_all_widgets()

    def on_opacity_text_changed(self, text):
        """Handle opacity text input change (real-time)"""
        if text and text.replace('.', '').isdigit():
            try:
                value = float(text)
                if 0 <= value <= 100:
                    self.preview_manager.set_foreground_opacity(value / 100.0)
            except ValueError:
                pass

    def on_opacity_editing_finished(self):
        """Handle opacity input when editing is finished"""
        value = self.controls_manager.opacity_input.value()
        if not value:
            self.controls_manager.opacity_input.setValue(50)
            self.preview_manager.set_foreground_opacity(0.5)
        else:
            try:
                value = max(0, min(100, float(value)))
                self.controls_manager.opacity_input.setValue(int(value))
                self.preview_manager.set_foreground_opacity(value / 100.0)
            except ValueError:
                current_percentage = int(self.preview_manager.foreground_opacity * 100)
                self.controls_manager.opacity_input.setValue(current_percentage)

    def on_show_date_changed(self, checked):
        """Handle show date checkbox change"""
        if self.date_widget:
            self.date_widget.set_enabled(checked)

    def on_show_time_changed(self, checked):
        """Handle show time checkbox change"""
        if self.time_widget:
            self.time_widget.set_enabled(checked)

    def on_metric_toggled(self, metric_name, checked):
        """Handle metric checkbox toggle"""
        if metric_name in self.metric_widgets:
            self.metric_widgets[metric_name].set_enabled(checked)

    def on_metric_label_changed(self, metric_name, text):
        """Handle metric label change"""
        if metric_name in self.metric_widgets:
            self.metric_widgets[metric_name].set_custom_label(text.strip())

    def on_metric_unit_changed(self, metric_name, text):
        """Handle metric unit change"""
        if metric_name in self.metric_widgets:
            self.metric_widgets[metric_name].set_custom_unit(text.strip())

    def on_collection_created(self, collection_path):
        """Handle collection creation"""
        self.on_background_clicked(collection_path)

    def on_background_clicked(self, file_path):
        """Handle background thumbnail click"""
        self.preview_manager.set_background(file_path)

    def on_foreground_clicked(self, file_path):
        """Handle foreground thumbnail click"""
        from pathlib import Path
        file_path_obj = Path(file_path)
        extension = file_path_obj.suffix.lower()
        supported_formats = self.config.get('supported_formats', {})
        image_extensions = set(supported_formats.get('images', []))

        if extension in image_extensions or extension == '.gif':
            self.preview_manager.set_foreground(file_path)
        else:
            self.preview_label.setText("Only images are supported\nfor foreground overlay")

    def clear_background(self):
        """Clear background media"""
        self.preview_manager.clear_background(self.backgrounds_dir)

    def clear_foreground(self):
        """Clear foreground media"""
        self.preview_manager.clear_foreground()

    def clear_all(self):
        """Clear all media"""
        self.preview_manager.clear_all(self.backgrounds_dir)

    def generate_config_yaml(self):
        """Generate YAML configuration file"""
        config_path = self.config_generator.generate_config_yaml(
            self.preview_manager, self.text_style, self.metric_widgets,
            self.date_widget, self.time_widget
        )
        if config_path:
            self.themes_tab.refresh_themes()

    def generate_preview(self):
        """Generate YAML configuration file"""
        self.config_generator.generate_config_yaml(
            self.preview_manager, self.text_style, self.metric_widgets,
            self.date_widget, self.time_widget, preview=True
        )

    def closeEvent(self, event):
        """Cleanup on close"""
        # Stop overlay widget timers
        for widget in [self.date_widget, self.time_widget]:
            if widget and hasattr(widget, 'update_timer'):
                widget.update_timer.stop()

        if self.preview_manager:
            self.preview_manager.cleanup()

        for tab in self.media_tabs:
            if hasattr(tab, 'cleanup_thumbnails'):
                tab.cleanup_thumbnails()

        super().closeEvent(event)
