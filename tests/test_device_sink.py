# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.frame_cache import FrameEncodeCache


class TestGenericSink(unittest.TestCase):
    def _device(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = g.GenericDisplayDevice.__new__(g.GenericDisplayDevice)
        dev.logger = mock.MagicMock()
        dev.width, dev.height = 4, 2
        dev.transport = mock.MagicMock()
        dev._encode_cache = FrameEncodeCache()
        dev._build_frame = mock.MagicMock(side_effect=lambda img: b"BYTES")
        return dev

    def test_encode_then_send_transmits_the_cached_frame(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        g.GenericDisplayDevice.encode_and_cache_frame(dev, 0, img)
        self.assertTrue(g.GenericDisplayDevice.send(dev, 0))
        dev.transport.send.assert_called_once_with(b"BYTES")

    def test_send_without_a_cached_frame_returns_false(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = self._device()
        self.assertFalse(g.GenericDisplayDevice.send(dev, 0))
        dev.transport.send.assert_not_called()

    def test_repeated_sends_replay_without_re_encoding(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        g.GenericDisplayDevice.encode_and_cache_frame(dev, 0, img)
        g.GenericDisplayDevice.send(dev, 0)
        g.GenericDisplayDevice.send(dev, 0)
        self.assertEqual(dev._build_frame.call_count, 1)   # encoded once
        self.assertEqual(dev.transport.send.call_count, 2)  # replayed twice


class TestLegacySink(unittest.TestCase):
    def _concrete_cls(self):
        from thermalright_lcd_control.device_controller.display import display_device as d

        class _Concrete(d.DisplayDevice):
            def get_header(self, *a, **k):
                return b"H"

            def send_packet(self, *a, **k):
                return None

        return _Concrete

    def _device(self):
        cls = self._concrete_cls()
        dev = cls.__new__(cls)
        dev.logger = mock.MagicMock()
        dev.width, dev.height = 4, 2
        dev.header = b"H"
        dev.chunk_size = 8
        dev.report_id = b"\x00"
        dev._encode_cache = FrameEncodeCache()
        dev._encode_image = mock.MagicMock(return_value=bytearray(b"PIX"))
        dev.send_packet = mock.MagicMock()
        return dev

    def test_encode_then_send_transmits_packets(self):
        from thermalright_lcd_control.device_controller.display import display_device as d
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        d.DisplayDevice.encode_and_cache_frame(dev, 0, img)
        self.assertTrue(d.DisplayDevice.send(dev, 0))
        self.assertEqual(dev._encode_image.call_count, 1)
        self.assertTrue(dev.send_packet.called)

    def test_send_without_a_cached_frame_returns_false(self):
        from thermalright_lcd_control.device_controller.display import display_device as d
        dev = self._device()
        self.assertFalse(d.DisplayDevice.send(dev, 0))
        dev.send_packet.assert_not_called()

    def test_repeated_sends_replay_without_re_encoding(self):
        from thermalright_lcd_control.device_controller.display import display_device as d
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        d.DisplayDevice.encode_and_cache_frame(dev, 0, img)
        d.DisplayDevice.send(dev, 0)
        d.DisplayDevice.send(dev, 0)
        self.assertEqual(dev._encode_image.call_count, 1)  # cached


class TestFrameEncodeCache(unittest.TestCase):
    """Entries are keyed on frame index alone; the bound tracks the clip size."""

    def test_set_frame_count_grows_limit(self):
        cache = FrameEncodeCache()
        cache.set_frame_count(300)
        for i in range(302):
            cache.store(i, b"x")
        self.assertEqual(len(cache), 302)   # clip + marge tient entièrement

    def test_eviction_bounds_cache(self):
        cache = FrameEncodeCache()
        cache.set_frame_count(300)
        for i in range(310):
            cache.store(i, b"x")            # 310 frames distinctes
        self.assertEqual(len(cache), 302)   # strictement borné (clip + marge)

    def test_reencode_replaces_entry_in_place(self):
        # Une nouvelle version d'overlay ré-encode chaque frame sur place :
        # aucune dimension de version, donc aucun doublon.
        cache = FrameEncodeCache(limit=8)
        cache.store(0, b"old")
        cache.store(0, b"new")
        self.assertEqual(cache.get(0), b"new")
        self.assertEqual(len(cache), 1)

    def test_clear_empties_the_cache(self):
        cache = FrameEncodeCache()
        cache.store(0, b"x")
        self.assertEqual(len(cache), 1)
        cache.clear()                       # appelé sur rebuild de config
        self.assertEqual(len(cache), 0)


if __name__ == "__main__":
    unittest.main()
