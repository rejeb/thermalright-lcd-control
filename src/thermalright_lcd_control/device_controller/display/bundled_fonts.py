# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Bundled fallback fonts shipped under ``resources/fonts``.

Used when fontconfig is unavailable or fails to resolve a requested family.
Every family ships the four (regular / bold / italic / bold-italic) faces, so
any (bold, italic) combination always resolves to a real file.
"""

from pathlib import Path

# resources/fonts relative to the repo root (…/src/thermalright_lcd_control/
# device_controller/display/bundled_fonts.py → up 5 → repo root)
_FONTS_DIR = Path(__file__).resolve().parents[4] / "resources" / "fonts"

# family → {(bold, italic): filename}
_REGISTRY: dict[str, dict[tuple[bool, bool], str]] = {
    "DejaVu Sans": {
        (False, False): "DejaVuSans.ttf",
        (True, False): "DejaVuSans-Bold.ttf",
        (False, True): "DejaVuSans-Oblique.ttf",
        (True, True): "DejaVuSans-BoldOblique.ttf",
    },
    "Liberation Sans": {
        (False, False): "LiberationSans-Regular.ttf",
        (True, False): "LiberationSans-Bold.ttf",
        (False, True): "LiberationSans-Italic.ttf",
        (True, True): "LiberationSans-BoldItalic.ttf",
    },
    "Liberation Serif": {
        (False, False): "LiberationSerif-Regular.ttf",
        (True, False): "LiberationSerif-Bold.ttf",
        (False, True): "LiberationSerif-Italic.ttf",
        (True, True): "LiberationSerif-BoldItalic.ttf",
    },
    "Liberation Mono": {
        (False, False): "LiberationMono-Regular.ttf",
        (True, False): "LiberationMono-Bold.ttf",
        (False, True): "LiberationMono-Italic.ttf",
        (True, True): "LiberationMono-BoldItalic.ttf",
    },
    "Noto Sans": {
        (False, False): "NotoSans-Regular.ttf",
        (True, False): "NotoSans-Bold.ttf",
        (False, True): "NotoSans-Italic.ttf",
        (True, True): "NotoSans-BoldItalic.ttf",
    },
}

# Proprietary names → bundled open substitutes.
_ALIASES = {
    "arial": "Liberation Sans",
    "helvetica": "Liberation Sans",
    "times new roman": "Liberation Serif",
    "times": "Liberation Serif",
    "courier new": "Liberation Mono",
    "courier": "Liberation Mono",
}

_DEFAULT_FAMILY = "DejaVu Sans"


def _canonical(family: str | None) -> str:
    if not family:
        return _DEFAULT_FAMILY
    if family in _REGISTRY:
        return family
    alias = _ALIASES.get(family.strip().lower())
    if alias:
        return alias
    # case-insensitive match against registered families
    for name in _REGISTRY:
        if name.lower() == family.strip().lower():
            return name
    return _DEFAULT_FAMILY


def resolve(family: str | None, bold: bool = False, italic: bool = False) -> str | None:
    """Absolute path to a bundled face for ``(family, bold, italic)``.

    Unknown families fall back to DejaVu Sans. Returns ``None`` only if the
    bundled file is genuinely missing on disk.
    """
    fam = _canonical(family)
    faces = _REGISTRY.get(fam, _REGISTRY[_DEFAULT_FAMILY])
    filename = faces.get((bool(bold), bool(italic))) or faces[(False, False)]
    path = _FONTS_DIR / filename
    return str(path) if path.is_file() else None


def families() -> list[str]:
    """Bundled family names (+ the well-known aliases) for UI listing."""
    names = list(_REGISTRY.keys())
    names += ["Arial", "Times New Roman", "Courier New"]
    return names
