# SPDX-License-Identifier: Apache-2.0
"""Media residency and the encoded-frame cache.

The render path is deliberately thin: _tick() advances timing and calls
sink.send(frame_idx), which replays an already-encoded frame from the device's
cache. Encoding happens off the render path, in the engine's background pass via
sink.encode_and_cache_frame(). The cache is keyed on frame index alone; a config
rebuild invalidates it wholesale."""
import threading
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import BackgroundType
from thermalright_lcd_control.device_controller.display.generator import DisplayGenerator
from thermalright_lcd_control.device_controller.display.render_engine import RenderEngine


class Cfg:
    def __init__(self, tmp_path):
        bg = tmp_path / "bg.png"
        vu.to_rgb(vu.solid(8, 6, (0, 0, 0, 255))).write_to_file(str(bg))
        self.background_path = str(bg)
        self.background_type = BackgroundType.IMAGE
        self.foreground_image_path = None
        self.foreground_position = (0, 0)
        self.foreground_alpha = 1.0
        self.output_width, self.output_height = 8, 6
        self.rotation = 0
        self.metrics_configs = []
        self.date_config = None
        self.time_config = None
        self.global_font_path = None



def test_metrics_dict_identity_stable_without_metrics(tmp_path):
    """sync_overlay() detects overlay refreshes by dict identity: without metric
    widgets get_current_metrics() must return the SAME object every call, or the
    overlay version bumps every tick and the encoded cache never hits."""
    gen = DisplayGenerator(Cfg(tmp_path))
    assert gen._metrics is None
    assert gen.get_current_metrics() is gen.get_current_metrics()
    gen.release()


# ── RenderEngine: render path ────────────────────────────────────────────────

class _CachingSink:
    """Device-like sink: send() replays a cached frame, encode_and_cache_frame()
    fills the cache from the background encode pass."""

    def __init__(self, cached=()):
        self._cached = set(cached)
        self.sent, self.encoded = [], []

    def send(self, frame_idx):
        self.sent.append(frame_idx)
        return frame_idx in self._cached

    def encode_and_cache_frame(self, frame_idx, img):
        self._cached.add(frame_idx)
        self.encoded.append(frame_idx)


def _fake_generator(version=7, resident=True):
    gen = mock.MagicMock()
    gen.get_base_frame.return_value = vu.to_rgb(vu.solid(4, 2, (1, 2, 3, 255)))
    gen.compose_device_frame.return_value = vu.to_rgb(vu.solid(4, 2, (4, 5, 6, 255)))
    gen.sync_overlay.return_value = version
    gen.peek_next_frame_idx.return_value = 0
    # The engine keys the send on the frame get_base_frame() just advanced to.
    gen.current_frame_index = 0
    gen.frame_duration = 0.0
    gen.frame_count = 2
    gen.media_resident = resident
    return gen


def _engine(sink=None, gen=None):
    eng = RenderEngine.__new__(RenderEngine)
    eng.width, eng.height = 4, 2
    eng.config_file = "/cfg/config_dev1.yaml"
    eng.logger = mock.MagicMock()
    eng._sink = sink
    eng._generator = gen or _fake_generator()
    eng._stop_event = threading.Event()
    eng._reload_requested = threading.Event()
    eng._pending_config = None
    eng._reload_id = "dev1"
    eng._event_bus = None
    eng._media_active = True
    eng._last_encoded_overlay_version = -1
    eng._encode_lock = threading.Lock()
    return eng


class _PlainSink:
    """Sink WITHOUT encode_and_cache_frame, so the background encode pass exits
    immediately and these tests observe the render path in isolation."""

    def __init__(self):
        self.sent = []

    def send(self, frame_idx):
        self.sent.append(frame_idx)
        return True


class TestTickMediaResidency(unittest.TestCase):
    def test_tick_ensures_media_when_not_resident(self):
        gen = _fake_generator(resident=False)
        eng = _engine(sink=_PlainSink(), gen=gen)
        eng._tick()
        gen.ensure_media.assert_called_once()
        gen.get_base_frame.assert_called_once()

    def test_tick_does_not_reload_resident_media(self):
        gen = _fake_generator(resident=True)
        eng = _engine(sink=_PlainSink(), gen=gen)
        eng._tick()
        gen.ensure_media.assert_not_called()

    def test_tick_sends_frame_index_without_composing(self):
        # The render path replays a pre-encoded frame; composition belongs to
        # the background encode pass, not to _tick.
        gen = _fake_generator(version=7)
        sink = _PlainSink()
        eng = _engine(sink=sink, gen=gen)
        eng._tick()
        self.assertEqual(sink.sent, [0])
        gen.compose_device_frame.assert_not_called()

    def test_tick_without_sink_only_advances_timing(self):
        gen = _fake_generator()
        eng = _engine(sink=None, gen=gen)
        delay = eng._tick()
        gen.get_base_frame.assert_called_once()
        gen.compose_device_frame.assert_not_called()
        self.assertEqual(delay, gen.frame_duration)


class TestBackgroundEncodePass(unittest.TestCase):
    """The pass composes and caches EVERY frame, so the render path only ever
    replays. This is what keeps compose off the tick."""

    def test_encode_pass_caches_every_frame(self):
        gen = _fake_generator(version=7)
        gen.frame_count = 2
        gen.frames = [(b"BASE0", 0.0), (b"BASE1", 0.0)]
        sink = _CachingSink()
        eng = _engine(sink=sink, gen=gen)

        eng._encode_all_frames(gen, 7)

        self.assertEqual(sorted(sink.encoded), [0, 1])
        self.assertTrue(sink.send(0))
        self.assertTrue(sink.send(1))

    def test_encode_pass_is_a_noop_without_an_encoding_sink(self):
        gen = _fake_generator(version=7)
        gen.frames = [(b"BASE0", 0.0)]
        eng = _engine(sink=_PlainSink(), gen=gen)

        eng._encode_all_frames(gen, 7)       # must not raise

        gen.compose_device_frame.assert_not_called()


class TestDisplayDeviceEncodeCache(unittest.TestCase):
    """send() replays cached bytes; encode_and_cache_frame() fills the cache.

    The cache is keyed on frame index alone — the overlay version is no longer
    part of the key, because a metrics change re-encodes every frame in place.
    """

    def _dev(self):
        from thermalright_lcd_control.device_controller.display.display_device import DisplayDevice
        from thermalright_lcd_control.device_controller.display.frame_cache import FrameEncodeCache

        class _Dev(DisplayDevice):
            def get_header(self):
                return b""

            def send_packet(self, packet):
                pass

        dev = _Dev.__new__(_Dev)
        dev.chunk_size = 8
        dev.report_id = b"\x00"
        dev.header = b""
        dev._encode_cache = FrameEncodeCache()
        dev.sent = []
        dev.send_packet = dev.sent.append
        return dev

    def test_send_miss_returns_false_and_sends_nothing(self):
        dev = self._dev()
        self.assertFalse(dev.send(0))
        self.assertEqual(dev.sent, [])

    def test_send_hit_sends_cached_packets(self):
        dev = self._dev()
        dev._encode_cache.store(0, b"ABCDEFGH")
        self.assertTrue(dev.send(0))
        self.assertEqual(dev.sent, [b"\x00ABCDEFGH"])

    def test_encode_and_cache_frame_makes_the_frame_sendable(self):
        dev = self._dev()
        dev._encode_image = lambda img: bytearray(b"ENCODED!")
        self.assertFalse(dev.send(3))          # nothing cached yet
        dev.encode_and_cache_frame(3, object())
        self.assertTrue(dev.send(3))

    def test_invalidate_cache_drops_encoded_frames(self):
        dev = self._dev()
        dev._encode_cache.store(0, b"ABCDEFGH")
        dev.invalidate_cache()
        self.assertFalse(dev.send(0))


class TestControllerMediaActive(unittest.TestCase):
    def _controller(self, active_id, engines):
        from thermalright_lcd_control.device_controller.controller import DeviceController
        ctl = DeviceController.__new__(DeviceController)
        ctl._media_active = True
        ctl.active_device_id = active_id
        ctl._loader = mock.MagicMock()
        ctl._loader.active_engines.return_value = engines
        return ctl

    def test_window_hidden_deactivates_all(self):
        e1, e2 = mock.MagicMock(_reload_id="dev1"), mock.MagicMock(_reload_id="dev2")
        ctl = self._controller(active_id="dev1", engines=[e1, e2])
        ctl.set_media_active(False)
        e1.set_media_active.assert_called_once_with(False)
        e2.set_media_active.assert_called_once_with(False)

    def test_only_active_device_keeps_media(self):
        e1, e2 = mock.MagicMock(_reload_id="dev1"), mock.MagicMock(_reload_id="dev2")
        ctl = self._controller(active_id="dev1", engines=[e1, e2])
        ctl.set_media_active(True)
        e1.set_media_active.assert_called_once_with(True)
        e2.set_media_active.assert_called_once_with(False)

    def test_no_active_id_keeps_all(self):
        e1, e2 = mock.MagicMock(_reload_id="dev1"), mock.MagicMock(_reload_id="dev2")
        ctl = self._controller(active_id=None, engines=[e1, e2])
        ctl.set_media_active(True)
        e1.set_media_active.assert_called_once_with(True)
        e2.set_media_active.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
