# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Modèle des widgets overlay : mêmes règles que l'ancienne UI web.

Un widget est un ``dict`` partagé tel quel avec ``AppBackend`` (add_widget /
update_widget / delete_widget) : ``{id, type, key, mode, group, text, unit,
prec, font_size, color, font_family, bold, italic, fx, fy, hidden, floating}``.
``fx``/``fy`` désignent le coin haut-gauche *visible* du texte (l'encre), en
fraction de la résolution device.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QFont, QFontMetricsF

# Précision par défaut : 0 pour toutes les métriques (bornée 0..2 à l'édition).
# Classées par périphérique : CPU, GPU, Memory, Disk, Network, System.
METRICS = {
    # CPU
    "cpu_temperature": {"label": "CPU", "unit": "°", "prec": 0, "val": 46},
    "cpu_usage": {"label": "CPU%", "unit": "%", "prec": 0, "val": 23.4},
    "cpu_frequency": {"label": "CPU", "unit": "MHZ", "prec": 0, "val": 4250},
    # GPU
    "gpu_temperature": {"label": "GPU", "unit": "°", "prec": 0, "val": 52},
    "gpu_usage": {"label": "GPU%", "unit": "%", "prec": 0, "val": 67.0},
    "gpu_frequency": {"label": "GPU", "unit": "MHZ", "prec": 0, "val": 1830},
    # Memory
    "memory_usage": {"label": "RAM%", "unit": "%", "prec": 0, "val": 42.0},
    "memory_used": {"label": "RAM", "unit": "GB", "prec": 1, "val": 6.7},
    "memory_available": {"label": "RAM FREE", "unit": "GB", "prec": 1, "val": 9.3},
    "swap_usage": {"label": "SWAP%", "unit": "%", "prec": 0, "val": 3.0},
    # Disk
    "disk_usage": {"label": "DISK%", "unit": "%", "prec": 0, "val": 58.0},
    "disk_read_speed": {"label": "READ", "unit": "MB/s", "prec": 1, "val": 12.4},
    "disk_write_speed": {"label": "WRITE", "unit": "MB/s", "prec": 1, "val": 3.8},
    # Network
    "net_download_speed": {"label": "DOWN", "unit": "MB/s", "prec": 1, "val": 2.1},
    "net_upload_speed": {"label": "UP", "unit": "MB/s", "prec": 1, "val": 0.4},
    # System
    "uptime": {"label": "UPTIME", "unit": "h", "prec": 1, "val": 5.2},
    "load_avg": {"label": "LOAD", "unit": "", "prec": 2, "val": 1.24},
    "process_count": {"label": "PROC", "unit": "", "prec": 0, "val": 312},
}
METRIC_NAMES = {
    "cpu_temperature": "CPU Temperature", "cpu_usage": "CPU Usage",
    "cpu_frequency": "CPU Frequency", "gpu_temperature": "GPU Temperature",
    "gpu_usage": "GPU Usage", "gpu_frequency": "GPU Frequency",
    "memory_usage": "Memory Usage", "memory_used": "Memory Used",
    "memory_available": "Memory Available", "swap_usage": "Swap Usage",
    "disk_usage": "Disk Usage", "disk_read_speed": "Disk Read",
    "disk_write_speed": "Disk Write", "net_download_speed": "Net Download",
    "net_upload_speed": "Net Upload", "uptime": "Uptime",
    "load_avg": "Load Average", "process_count": "Processes",
}

PREC_MIN, PREC_MAX = 0, 2
# Editing bound for the font spinbox / resize handles. Raised well above the old
# 72 so configs imported from large panels (device fonts up to ~128 px) can be
# represented and edited rather than snapped down.
FONT_MIN, FONT_MAX = 8, 256

# Glyphes de référence pour mesurer le décalage d'encre — identiques au backend
# (_GAP_REF), pour un ancrage cohérent preview/device.
INK_REF = "ACGgjpq0123456789:%°"

DEFAULT_STYLE = {"font_size": 18, "color": "#FFFFFF", "font_family": None,
                 "bold": False, "italic": False}


def clamp_prec(p) -> int:
    try:
        p = int(p)
    except (TypeError, ValueError):
        p = 0
    return max(PREC_MIN, min(PREC_MAX, p))


def clamp_font(size) -> int:
    """Bound a font size to the EDITING range (spinbox / resize handles)."""
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 18
    return max(FONT_MIN, min(FONT_MAX, size))


def display_font(size) -> int:
    """Pixel size for RENDERING a widget's text in the preview — must match the
    device renderer, which applies no upper cap. Only a lower floor is enforced;
    the ``FONT_MAX`` editing bound is deliberately NOT applied so an imported
    config previews at its true (possibly very large) size."""
    try:
        return max(FONT_MIN, int(round(float(size))))
    except (TypeError, ValueError):
        return 18


def clock_text(w: dict) -> str:
    now = datetime.now()
    mode = w.get("mode")
    if mode == "date":
        return now.strftime("%d/%m")
    if mode == "weekday":
        return now.strftime("%A")
    return now.strftime("%H:%M")


_NO_LIVE = object()


def metric_text(w: dict, live_metrics: dict) -> str:
    """Valeur affichée d'une métrique (le label est toujours un widget séparé).

    Sans donnée live (préview jamais rafraîchi), la valeur d'exemple du
    catalogue est montrée. Une sonde réellement indisponible (valeur ``None``
    dans le live) affiche ``--`` : le device ne rendra pas ce widget, le
    preview ne doit pas faire croire le contraire avec un nombre plausible."""
    raw = live_metrics.get(w.get("key"), _NO_LIVE)
    if raw is _NO_LIVE:
        raw = METRICS.get(w.get("key"), {}).get("val", 0)
    elif raw is None:
        return "--"
    try:
        value = f"{float(raw):.{clamp_prec(w.get('prec', 0))}f}"
    except (TypeError, ValueError):
        value = "0"
    return value + (w.get("unit") or "")


def widget_text(w: dict, live_metrics: dict) -> str:
    if w.get("type") == "clock":
        return clock_text(w)
    if w.get("type") == "metric":
        return metric_text(w, live_metrics)
    return w.get("text") or "Label"


def widget_font(w: dict) -> QFont:
    """QFont du widget à l'échelle device (pixels) — la vue applique le zoom."""
    font = QFont(w.get("font_family") or "")
    font.setPixelSize(display_font(w.get("font_size", 18)))
    font.setBold(bool(w.get("bold")))
    font.setItalic(bool(w.get("italic")))
    return font


_INK_CACHE: dict[tuple, tuple[float, float]] = {}


def ink_offset(font: QFont) -> tuple[float, float]:
    """Décalage (px) entre l'origine de dessin d'un item texte (top-left de la
    boîte) et le coin haut-gauche réel de l'encre — équivalent Qt du
    ``_text_anchor_gap`` du backend."""
    key = (font.family(), font.pixelSize(), font.bold(), font.italic())
    cached = _INK_CACHE.get(key)
    if cached is not None:
        return cached
    fm = QFontMetricsF(font)
    tight = fm.tightBoundingRect(INK_REF)
    # QGraphicsSimpleTextItem dessine la baseline à ``ascent()`` sous le haut de
    # l'item ; l'encre commence à ``ascent + tight.y()`` (tight.y() < 0).
    off = (max(0.0, tight.x()), max(0.0, fm.ascent() + tight.y()))
    _INK_CACHE[key] = off
    return off


def label_of(widgets: list[dict], metric: dict) -> dict | None:
    """Le widget label lié à une métrique (même ``group``)."""
    return next((x for x in widgets
                 if x.get("type") == "metric_label"
                 and x.get("group") == metric.get("group")), None)


def metric_of(widgets: list[dict], label: dict) -> dict | None:
    return next((x for x in widgets
                 if x.get("type") == "metric"
                 and x.get("group") == label.get("group")), None)


def effective_move_set(widgets: list[dict], ids: set) -> set:
    """Ids réellement déplacés : une valeur rigide entraîne son label (et
    inversement) ; en mode ``floating`` le label reste indépendant."""
    out = set(ids)
    for wid in list(ids):
        w = next((x for x in widgets if x.get("id") == wid), None)
        if w is None:
            continue
        if w.get("type") == "metric":
            lw = label_of(widgets, w)
            if lw and not lw.get("floating"):
                out.add(lw["id"])
        elif w.get("type") == "metric_label" and not w.get("floating"):
            m = metric_of(widgets, w)
            if m:
                out.add(m["id"])
    return out
