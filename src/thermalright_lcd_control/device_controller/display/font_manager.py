# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import os
import re
import subprocess

from dataclasses import dataclass

from thermalright_lcd_control.common.logging_config import LoggerConfig
from thermalright_lcd_control.device_controller.display import bundled_fonts
from thermalright_lcd_control.device_controller.display.utils import _get_default_font_path

# Icon / symbol / emoji fonts have no Latin text glyphs, so any text rendered
# with them shows as .notdef boxes (▯). Filter them out of the picker by name,
# on top of the ``:lang=en`` fontconfig filter (which already drops most of them).
_SYMBOL_FONT_RE = re.compile(
    r"awesome|emoji|symbol|icons?|dingbat|webding|wingding|glyphicon",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResolvedFont:
    """A concrete font choice: file path (may be None), family name, pixel size."""
    path: str | None
    family: str
    size: int


def pango_font_string(rf: "ResolvedFont", bold: bool = False, italic: bool = False) -> str:
    """Pango font description; size is px because the renderer uses dpi=72."""
    parts = [rf.family]
    if bold:
        parts.append("Bold")
    if italic:
        parts.append("Italic")
    parts.append(str(rf.size))
    return " ".join(parts)


def _fc_family_of_file(path: str) -> str | None:
    """Family name embedded in a font file (Pango needs the name, not the path)."""
    try:
        out = subprocess.check_output(
            ["fc-scan", "--format=%{family[0]}", path], text=True).strip()
        return out or None
    except Exception:
        return None


def _fc_match(pattern: str) -> str:
    """Return the font file path fontconfig picks for ``pattern`` (may raise)."""
    return subprocess.check_output(
        ["fc-match", "--format=%{file}", pattern], text=True
    ).strip()


def _fc_list() -> list[str]:
    """Return installed *text* family names via fontconfig (may raise).

    Restricted to fonts that cover the English (basic Latin) charset via
    ``:lang=en`` and further filtered to drop icon/symbol/emoji families that
    would render text as empty boxes.
    """
    out = subprocess.check_output(["fc-list", ":lang=en", "family"], text=True)
    names: set[str] = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        name = line.split(",")[0].strip()
        if name and not _SYMBOL_FONT_RE.search(name):
            names.add(name)
    return sorted(names)


def _fc_pattern(family: str | None, bold: bool, italic: bool) -> str:
    parts = [family or ""]
    if bold:
        parts.append("weight=bold")
    if italic:
        parts.append("slant=italic")
    return ":".join(parts)


class SystemFontManager:
    """Resolve fonts by (family, bold, italic, size) with caching.

    fontconfig is the primary source; bundled files under ``resources/fonts``
    are the fallback. ``get_font(size)`` with no style keeps the historical
    default font, so existing configs render identically.
    """

    def __init__(self):
        self.logger = LoggerConfig.setup_service_logger()
        self.font_path = _get_default_font_path()
        self._font_cache: dict[tuple, ResolvedFont] = {}
        self._path_cache: dict[tuple[str, bool, bool], str | None] = {}

    def resolve_font_path(self, family: str | None, bold: bool, italic: bool) -> str | None:
        """Concrete font file for the request, via fontconfig then bundled."""
        key = (family or "", bool(bold), bool(italic))
        if key in self._path_cache:
            return self._path_cache[key]
        path: str | None = None
        try:
            candidate = _fc_match(_fc_pattern(family, bold, italic))
            if candidate and os.path.isfile(candidate):
                path = candidate
        except Exception as e:  # fontconfig missing / failed
            self.logger.warning(f"fc-match failed for {family!r}: {e}")
        if path is None:
            path = bundled_fonts.resolve(family, bold, italic)
        self._path_cache[key] = path
        return path

    def get_font(self, font_size: int, family: str | None = None,
                 bold: bool = False, italic: bool = False) -> ResolvedFont:
        """Cached resolved font. No style args → historical default font file."""
        key = (family or "", bool(bold), bool(italic), int(font_size))
        if key in self._font_cache:
            return self._font_cache[key]

        if not family and not bold and not italic:
            path = self.font_path if self.font_path and os.path.isfile(self.font_path) else None
        else:
            path = self.resolve_font_path(family, bold, italic)
            if path and not os.path.isfile(path):
                path = None

        fam = (family
               or (path and _fc_family_of_file(path))
               or "sans")
        rf = ResolvedFont(path=path, family=fam, size=int(font_size))
        self._font_cache[key] = rf
        return rf


# Global font manager instance
_font_manager: SystemFontManager | None = None


def get_font_manager() -> SystemFontManager:
    """Get the global font manager instance"""
    global _font_manager
    if _font_manager is None:
        _font_manager = SystemFontManager()
    return _font_manager


def list_font_families() -> list[str]:
    """Sorted unique family names for the UI. fontconfig → bundled fallback."""
    try:
        fams = _fc_list()
        if fams:
            return fams
    except Exception:
        pass
    return sorted(bundled_fonts.families())
