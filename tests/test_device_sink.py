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

    def test_send_image_encodes_and_sends(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        g.GenericDisplayDevice.send_image(dev, img, frame_idx=0, overlay_version=3)
        dev.transport.send.assert_called_once_with(b"BYTES")

    def test_send_image_caches_by_idx_and_version(self):
        from thermalright_lcd_control.device_controller.display import generic_display_device as g
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        g.GenericDisplayDevice.send_image(dev, img, 0, 3)
        g.GenericDisplayDevice.send_image(dev, img, 0, 3)  # same key → no re-encode
        self.assertEqual(dev._build_frame.call_count, 1)
        self.assertEqual(dev.transport.send.call_count, 2)


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

    def test_send_image_encodes_and_sends_packets(self):
        from thermalright_lcd_control.device_controller.display import display_device as d
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        d.DisplayDevice.send_image(dev, img, 0, 5)
        self.assertEqual(dev._encode_image.call_count, 1)
        self.assertTrue(dev.send_packet.called)

    def test_send_image_caches_by_idx_and_version(self):
        from thermalright_lcd_control.device_controller.display import display_device as d
        dev = self._device()
        img = vu.to_rgb(vu.solid(4, 2, (0, 0, 0, 255)))
        d.DisplayDevice.send_image(dev, img, 0, 5)
        d.DisplayDevice.send_image(dev, img, 0, 5)
        self.assertEqual(dev._encode_image.call_count, 1)  # cached


class TestFrameEncodeCache(unittest.TestCase):
    def test_set_frame_count_grows_limit(self):
        cache = FrameEncodeCache()
        cache.set_frame_count(300)
        for i in range(302):
            cache.store(i, 0, b"x")
        self.assertEqual(len(cache), 302)   # clip + marge tient entièrement

    def test_eviction_bounds_cache_even_within_one_version(self):
        cache = FrameEncodeCache()
        cache.set_frame_count(300)
        for i in range(310):
            cache.store(i, 0, b"x")         # 310 frames, même version
        self.assertEqual(len(cache), 302)   # strictement borné (clip + marge)

    def test_store_evicts_stale_overlay_versions(self):
        cache = FrameEncodeCache(limit=2)
        for i in range(5):
            cache.store(i, 0, b"old")
        cache.store(0, 1, b"new")
        self.assertEqual(cache.get(0, 1), b"new")
        self.assertIsNone(cache.get(0, 0))  # v0 purgé
        self.assertEqual(len(cache), 1)

    def test_sync_generator_clears_on_change(self):
        cache = FrameEncodeCache()
        cache.sync_generator(111)
        cache.store(0, 0, b"x")
        cache.sync_generator(111)           # même générateur → conservé
        self.assertEqual(len(cache), 1)
        cache.sync_generator(222)           # nouveau générateur → vidé
        self.assertEqual(len(cache), 0)


if __name__ == "__main__":
    unittest.main()
