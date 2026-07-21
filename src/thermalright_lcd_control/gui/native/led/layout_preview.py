# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""LED layout preview widget. Repaints from shared effects.compute()."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ....device_controller.led.effects import compute
from ....device_controller.led.geometry import geometry_for

_MAX_FPS = 20


class LayoutPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self.setMaximumHeight(560)
        self._style_info = None
        self._settings = None
        self._metrics = {}
        self._tick = 0
        self._colors = []
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _MAX_FPS))
        self._timer.timeout.connect(self.advance)

    def set_style(self, style_info):
        self._style_info = style_info

    def set_settings(self, settings):
        self._settings = settings

    def set_metrics(self, metrics):
        self._metrics = metrics

    def current_colors(self):
        return list(self._colors)

    def start(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()

    def advance(self):
        if not self.isVisible() or self._style_info is None or self._settings is None:
            return
        res = compute(self._settings, self._style_info, self._tick, self._metrics)
        self._colors = [
            (r, g, b) if on else (0, 0, 0)
            for (r, g, b), on in zip(res.colors, res.is_on)
        ]
        self._tick += 1
        self.update()

    def hideEvent(self, event):
        self.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # The device face is black; unlit LEDs are invisible on hardware. Paint
        # a dark backdrop so lit segments/digits pop and off LEDs recede.
        painter.fillRect(self.rect(), QColor(12, 12, 12))
        if self._style_info is None or not self._colors:
            painter.end()
            return
        pts = geometry_for(self._style_info.style)
        # Fit the layout's ACTUAL bounding box (not the raw 460x460 firmware
        # frame) into the widget, centred, preserving aspect ratio. Some styles
        # (e.g. LF10) only occupy a sub-region of the firmware frame, so a fixed
        # normalization would draw them small and off-centre.
        minx = min(p.x for p in pts)
        miny = min(p.y for p in pts)
        maxx = max(p.x + p.w for p in pts)
        maxy = max(p.y + p.h for p in pts)
        bw = max(1e-6, maxx - minx)
        bh = max(1e-6, maxy - miny)

        pad = 0.06
        avail_w = self.width() * (1 - 2 * pad)
        avail_h = self.height() * (1 - 2 * pad)
        scale = min(avail_w / bw, avail_h / bh)
        draw_w = bw * scale
        draw_h = bh * scale
        ox = (self.width() - draw_w) / 2
        oy = (self.height() - draw_h) / 2

        painter.setPen(Qt.PenStyle.NoPen)
        for pt, col in zip(pts, self._colors):
            # Off LEDs (black) draw as a faint outline so the fixed layout stays
            # readable without competing with lit segments.
            painter.setBrush(QColor(34, 34, 34) if col == (0, 0, 0) else QColor(*col))
            x = ox + (pt.x - minx) * scale
            y = oy + (pt.y - miny) * scale
            w = max(2.0, pt.w * scale)
            h = max(2.0, pt.h * scale)
            r = min(w, h) * 0.35
            painter.drawRoundedRect(x, y, w, h, r, r)
        painter.end()
