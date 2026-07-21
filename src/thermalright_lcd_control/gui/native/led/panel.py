# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Kind-switched LED control panel. Hosts sections gated by style flags."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from .advanced_section import AdvancedSection
from .color_section import ColorSection
from .mode_section import ModeSection
from .zone_section import ZoneSection


class LedPanel(QWidget):
    def __init__(self, on_change, parent=None) -> None:
        super().__init__(parent)
        self._on_change = on_change
        # NOTE: no "segments" section — per-segment on/off is vestigial (the
        # reference trcc stores it but never applies it to the rendered output),
        # so exposing it would be a control that does nothing. Removed.
        self._sections = {
            "color": ColorSection(on_change, self),
            "mode": ModeSection(on_change, self),
            "zones": ZoneSection(on_change, self),
            "advanced": AdvancedSection(on_change, self),
        }
        root = QVBoxLayout(self)
        for w in self._sections.values():
            root.addWidget(w)
        root.addStretch(1)

    def apply_theme(self, mode: str) -> None:
        """Style the sections from the app's theme tokens so labels, group
        titles and controls stay legible in both dark and light themes. The
        global QSS only styles object-named widgets, so the LED panel's plain
        QLabel/QGroupBox/QRadioButton would otherwise use the default palette.
        Colour swatch/preset buttons keep their own inline background."""
        from thermalright_lcd_control.gui.native.theme import tokens
        t = tokens(mode)
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {t['dim']};
                border: 1px solid {t['line_strong']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px 8px 8px 8px;
                font-weight: 700;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
            QRadioButton, QCheckBox {{ color: {t['text']}; background: transparent; }}
            QSpinBox {{
                color: {t['text']}; background: {t['card']};
                border: 1px solid {t['line_strong']}; border-radius: 6px;
                padding: 2px 4px;
            }}
            QPushButton {{
                color: {t['text']}; background: {t['card']};
                border: 1px solid {t['line_strong']}; border-radius: 6px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ background: {t['hover']}; }}
            QSlider::groove:horizontal {{ height: 4px; background: {t['off']}; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
            QSlider::handle:horizontal {{
                background: {t['text']}; width: 12px; margin: -5px 0; border-radius: 6px;
            }}
        """)

    def apply_style(self, style_info) -> None:
        self._sections["color"].setVisible(True)
        self._sections["mode"].setVisible(True)
        self._sections["zones"].setVisible(style_info.has_zones)
        adv = (style_info.has_sensors or style_info.has_clock
               or style_info.has_memory_disk)
        self._sections["advanced"].setVisible(adv)

    def load_settings(self, settings) -> None:
        for w in self._sections.values():
            w.load_settings(settings)

    def section_visible(self, name: str) -> bool:
        return self._sections[name].isVisibleTo(self)
