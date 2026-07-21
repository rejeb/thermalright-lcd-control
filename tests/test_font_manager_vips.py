# SPDX-License-Identifier: Apache-2.0
from thermalright_lcd_control.device_controller.display.font_manager import (
    ResolvedFont,
    get_font_manager,
    pango_font_string,
)


def test_get_font_returns_resolved_font():
    rf = get_font_manager().get_font(18)
    assert isinstance(rf, ResolvedFont)
    assert rf.size == 18
    assert rf.family            # fc-match always yields a family name
    assert rf.path is None or rf.path.endswith((".ttf", ".otf", ".ttc"))


def test_pango_font_string_styles():
    rf = ResolvedFont(path=None, family="DejaVu Sans", size=20)
    assert pango_font_string(rf, bold=True, italic=False) == "DejaVu Sans Bold 20"
    assert pango_font_string(rf, bold=True, italic=True) == "DejaVu Sans Bold Italic 20"
    assert pango_font_string(rf, bold=False, italic=False) == "DejaVu Sans 20"
