# SPDX-License-Identifier: Apache-2.0
"""Backend slot get_supported_resolutions(): parse the <width><height> folder
names under backgrounds_base into the list of device resolutions.

Folder names are ambiguous digit concatenations (e.g. ``1920462``) and exist in
both orders (wxh and hxw). Device spec: width >= height, width <= 1920 — only
splits satisfying that are device resolutions; non-digit names (variant
suffixes like ``1600720u``, the ``{resolution}`` placeholder) are ignored.
"""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _backend(bg_base):
    from thermalright_lcd_control.gui.backend.app_backend import AppBackend
    cfg = {"paths": {"backgrounds_dir": str(bg_base)}, "supported_formats": {}}
    return AppBackend(cfg, [], event_bus=None)


class TestSupportedResolutions(unittest.TestCase):
    def setUp(self):
        _app()

    def test_parses_both_orders_suffixes_and_placeholder(self):
        with TemporaryDirectory() as d:
            for name in ("320240", "240320",        # 320x240 both orders
                         "1920462", "4621920",      # 1920x462
                         "1600720", "7201600",      # 1600x720
                         "1600720u", "1600720l",    # variant suffixes → ignored
                         "360360",                  # square
                         "{resolution}"):           # placeholder → ignored
                (Path(d) / name).mkdir()
            be = _backend(d)
            res = json.loads(be.get_supported_resolutions())
            self.assertEqual(res, [[320, 240], [360, 360],
                                   [1600, 720], [1920, 462]])

    def test_real_resources_folder(self):
        be = _backend("resources/themes/backgrounds")
        res = [tuple(r) for r in json.loads(be.get_supported_resolutions())]
        # spot-check known devices; every entry respects w >= h and w <= 1920
        for expected in [(320, 240), (480, 480), (640, 172), (854, 480),
                         (960, 540), (1280, 480), (1600, 720),
                         (1920, 440), (1920, 462)]:
            self.assertIn(expected, res)
        # ambiguous splits of hxw folders must not leak through
        # (e.g. "172640" also splits as 1726x40)
        self.assertNotIn((1726, 40), res)
        self.assertNotIn((1763, 20), res)
        for w, h in res:
            self.assertGreaterEqual(w, h, (w, h))
            self.assertLessEqual(w, 1920, (w, h))


if __name__ == "__main__":
    unittest.main()
