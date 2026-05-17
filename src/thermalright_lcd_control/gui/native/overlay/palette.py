# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Palette de widgets overlay : tuiles Clock / CPU / GPU à glisser sur le preview.

Le drag utilise un ``QDrag`` avec le mime ``application/x-trlcd-widget``
(payload JSON ``{type, key, mode}``) consommé par :class:`PreviewView`.
La tuile Clock porte un mini-sélecteur Date/Time qui fixe le mode du prochain
widget déposé, comme dans l'UI web.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.overlay.view import MIME_WIDGET

# Clock tiles carry their mode in the ``key`` slot (date / time / weekday); the
# drop payload's ``mode`` drives the created widget (cf. editor.add_widget).
_TILES = [
    ("clock", "time", "Time", "HH:MM", "14:30"),
    ("clock", "date", "Date", "dd/mm", "31/12"),
    ("clock", "weekday", "Day of week", "Weekday name", "Monday"),
    ("text", None, "Text", "Custom label / title", "Text"),
    ("_grp", None, "CPU", None, None),
    ("metric", "cpu_temperature", "CPU Temp", "Temperature", "46°"),
    ("metric", "cpu_usage", "CPU Usage", "Load %", "23%"),
    ("metric", "cpu_frequency", "CPU Freq", "Frequency", "4250MHZ"),
    ("_grp", None, "GPU", None, None),
    ("metric", "gpu_temperature", "GPU Temp", "Temperature", "52°"),
    ("metric", "gpu_usage", "GPU Usage", "Load %", "67%"),
    ("metric", "gpu_frequency", "GPU Freq", "Frequency", "1830MHZ"),
    ("_grp", None, "Memory", None, None),
    ("metric", "memory_usage", "RAM Usage", "Load %", "42%"),
    ("metric", "memory_used", "RAM Used", "Gigabytes", "6.7GB"),
    ("metric", "memory_available", "RAM Free", "Gigabytes", "9.3GB"),
    ("metric", "swap_usage", "Swap Usage", "Load %", "3%"),
    ("_grp", None, "Disk", None, None),
    ("metric", "disk_usage", "Disk Usage", "Filesystem %", "58%"),
    ("metric", "disk_read_speed", "Disk Read", "Throughput", "12.4MB/s"),
    ("metric", "disk_write_speed", "Disk Write", "Throughput", "3.8MB/s"),
    ("_grp", None, "Network", None, None),
    ("metric", "net_download_speed", "Download", "Throughput", "2.1MB/s"),
    ("metric", "net_upload_speed", "Upload", "Throughput", "0.4MB/s"),
    ("_grp", None, "System", None, None),
    ("metric", "uptime", "Uptime", "Hours", "5.2h"),
    ("metric", "load_avg", "Load Avg", "1 min", "1.24"),
    ("metric", "process_count", "Processes", "Count", "312"),
]


class _Tile(QFrame):
    def __init__(self, palette: WidgetPalette, wtype: str, key: str | None,
                 name: str, sub: str, sample: str):
        super().__init__()
        self.setObjectName("card")
        self.setCursor(Qt.OpenHandCursor)
        self._palette = palette
        self._wtype = wtype
        self._key = key
        self._press: QPoint | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        text = QVBoxLayout()
        text.setSpacing(1)
        nm = QLabel(name)
        sb = QLabel(sub)
        sb.setObjectName("faintText")
        text.addWidget(nm)
        text.addWidget(sb)
        lay.addLayout(text)
        lay.addStretch(1)
        val = QLabel(sample)
        val.setObjectName("dimText")
        lay.addWidget(val)

    def _mode(self) -> str:
        # Clock tiles carry their mode (date / time / weekday) in ``key``.
        return self._key if self._wtype == "clock" else "time"

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press is None:
            return super().mouseMoveEvent(e)
        if (e.position().toPoint() - self._press).manhattanLength() < 8:
            return
        self._press = None
        drag = QDrag(self)
        mime = QMimeData()
        payload = {"type": self._wtype, "key": self._key, "mode": self._mode()}
        mime.setData(MIME_WIDGET, json.dumps(payload).encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.CopyAction)

    def mouseReleaseEvent(self, e):
        self._press = None
        super().mouseReleaseEvent(e)


class WidgetPalette(QWidget):
    """Liste scrollable des tuiles + pied d'aide (onglet « Overlay widgets »)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        head = QHBoxLayout()
        title = QLabel("Widgets")
        title.setObjectName("sectionTitle")
        hint = QLabel("Drag onto the screen →")
        hint.setObjectName("faintText")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(hint)
        root.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(8)
        for wtype, key, name, sub, sample in _TILES:
            if wtype == "_grp":
                grp = QLabel(name)
                grp.setObjectName("accentText")
                lay.addWidget(grp)
                continue
            lay.addWidget(_Tile(self, wtype, key, name, sub, sample))
        lay.addStretch(1)
        scroll.setWidget(inner)
        scroll.viewport().setAutoFillBackground(False)
        inner.setAutoFillBackground(False)
        root.addWidget(scroll, 1)

        foot = QLabel("Drop a widget on the screen, drag to position. Select to edit.")
        foot.setObjectName("faintText")
        foot.setWordWrap(True)
        root.addWidget(foot)
