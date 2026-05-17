# SPDX-License-Identifier: Apache-2.0
from thermalright_lcd_control.common import media_formats as mf


def test_image_extensions_lowercase_and_dotted():
    assert ".png" in mf.IMAGE_EXTENSIONS
    assert all(e.startswith(".") and e == e.lower() for e in mf.IMAGE_EXTENSIONS)


def test_is_video():
    assert mf.is_video("/x/clip.MP4")
    assert not mf.is_video("/x/photo.png")
