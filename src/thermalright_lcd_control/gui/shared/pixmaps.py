# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Conversions image → QPixmap partagées par l'UI native.

Deux sources : les thumbnails du backend (data-URLs PNG base64, format hérité de
l'UI web et conservé tel quel) et les images pyvips (chemin rapide, sans
encodage intermédiaire).
"""

from __future__ import annotations

import base64

from PySide6.QtGui import QImage, QPixmap


def pixmap_from_data_url(url: str) -> QPixmap:
    """Décode un ``data:image/...;base64,...`` en QPixmap (vide si invalide)."""
    pm = QPixmap()
    if not url or "," not in url:
        return pm
    try:
        pm.loadFromData(base64.b64decode(url.split(",", 1)[1]))
    except Exception:
        return QPixmap()
    return pm


def pixmap_from_vips(img) -> QPixmap:
    """pyvips.Image → QPixmap sans passer par un encodage PNG/JPEG.

    Copie le buffer : QImage référencerait sinon la mémoire du
    ``write_to_memory()`` temporaire, libérée au retour."""
    if img.hasalpha():
        if img.bands != 4:
            img = img.colourspace("srgb")
        fmt, channels = QImage.Format_RGBA8888, 4
    else:
        if img.bands != 3:
            img = img.colourspace("srgb")
        fmt, channels = QImage.Format_RGB888, 3
    data = img.write_to_memory()
    qimg = QImage(data, img.width, img.height, img.width * channels, fmt).copy()
    return QPixmap.fromImage(qimg)
