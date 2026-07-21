# SPDX-License-Identifier: Apache-2.0
"""Low-memory mode (window minimized to tray): the generator's composed frame
cache is dropped, only the sink's ready-to-send encoded cache stays resident.
On an encoded-cache miss the clip is re-read once (warm-up), then re-dropped."""
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


# ── RenderEngine: minimized tick ─────────────────────────────────────────────

class _CachingSink:
    def __init__(self, cached=()):
        self._cached = set(cached)
        self.resent, self.sent = [], []

    def resend(self, frame_idx, overlay_version):
        if (frame_idx, overlay_version) in self._cached:
            self.resent.append((frame_idx, overlay_version))
            return True
        return False

    def send_image(self, img, frame_idx, overlay_version):
        self.sent.append((frame_idx, overlay_version))


def _fake_generator(version=7, resident=True):
    gen = mock.MagicMock()
    gen.get_base_frame.return_value = vu.to_rgb(vu.solid(4, 2, (1, 2, 3, 255)))
    gen.compose_device_frame.return_value = vu.to_rgb(vu.solid(4, 2, (4, 5, 6, 255)))
    gen.sync_overlay.return_value = version
    gen.peek_next_frame_idx.return_value = 0
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
    return eng


class TestMinimizedTick(unittest.TestCase):
    def test_minimized_cache_hit_drops_media(self):
        gen = _fake_generator()
        eng = _engine(sink=_CachingSink({(0, 7)}), gen=gen)
        eng.set_media_active(False)
        eng._tick()
        gen.drop_media.assert_called_once()
        gen.get_base_frame.assert_not_called()

    def test_minimized_cache_hit_serves_resend_without_compose(self):
        gen = _fake_generator(version=7)
        sink = _CachingSink({(0, 7)})
        eng = _engine(sink=sink, gen=gen)
        eng.set_media_active(False)
        eng._tick()
        self.assertEqual(sink.resent, [(0, 7)])
        gen.compose_device_frame.assert_not_called()

    def test_minimized_cache_miss_reloads_and_sends(self):
        gen = _fake_generator(version=7, resident=False)
        sink = _CachingSink(set())
        eng = _engine(sink=sink, gen=gen)
        eng.set_media_active(False)
        eng._tick()
        gen.ensure_media.assert_called_once()
        gen.compose_device_frame.assert_called_once()
        self.assertEqual(sink.sent, [(0, 7)])
        gen.drop_media.assert_not_called()   # keeps warm until next resend hit

    def test_minimized_preview_only_engine_drops_and_idles(self):
        gen = _fake_generator()
        eng = _engine(sink=None, gen=gen)
        eng.set_media_active(False)
        delay = eng._tick()
        gen.drop_media.assert_called_once()
        gen.get_base_frame.assert_not_called()
        self.assertEqual(delay, 1.0)

    def test_restore_reloads_media(self):
        gen = _fake_generator(resident=False)
        eng = _engine(sink=_CachingSink({(0, 7)}), gen=gen)
        eng.set_media_active(True)
        eng._tick()
        gen.ensure_media.assert_called_once()
        gen.get_base_frame.assert_called_once()


class TestDisplayDeviceResend(unittest.TestCase):
    def _sink(self):
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
        dev._encode_cache = FrameEncodeCache()
        dev.sent = []
        dev.send_packet = dev.sent.append
        return dev

    def test_resend_miss_returns_false(self):
        dev = self._sink()
        self.assertFalse(dev.resend(0, 1))
        self.assertEqual(dev.sent, [])

    def test_resend_hit_sends_cached_packets(self):
        dev = self._sink()
        dev._encode_cache.store(0, 1, b"ABCDEFGH")
        self.assertTrue(dev.resend(0, 1))
        self.assertEqual(dev.sent, [b"\x00ABCDEFGH"])


def _straddle_gen(version=7):
    """A generator whose get_base_frame() advances the current index past a
    frame boundary (0 → 1), while peek_next_frame_idx() still reports the stale
    pre-advance index 0. A correct _run keys the encode cache on the frame it
    actually rendered (current_frame_index == 1), not the stale peek (0)."""
    gen = mock.MagicMock()
    gen.current_frame_index = 0
    gen.peek_next_frame_idx.return_value = 0

    def advance_and_return():
        gen.current_frame_index = 1
        return "BASE"

    gen.get_base_frame.side_effect = advance_and_return
    gen.compose_device_frame.return_value = "IMG"
    gen.sync_overlay.return_value = version
    gen.frame_duration = 0.0
    gen.frame_count = 2
    return gen


class TestRunCacheKeyMatchesRenderedFrame(unittest.TestCase):
    """The standalone _run loops must store the encoded frame under the index
    they actually rendered, not a pre-advance peek — otherwise a tick that
    straddles a frame boundary poisons the encode cache (regression guard)."""

    def test_generic_display_device_keys_on_current_index(self):
        from thermalright_lcd_control.device_controller.display.frame_cache import (
            FrameEncodeCache,
        )
        from thermalright_lcd_control.device_controller.display.generic_display_device import (
            GenericDisplayDevice,
        )
        gen = _straddle_gen()
        dev = GenericDisplayDevice.__new__(GenericDisplayDevice)
        dev._encode_cache = FrameEncodeCache()
        dev.transport = mock.MagicMock()
        dev._get_generator = lambda: gen
        dev._build_frame = lambda img: b"ENC"

        dev._run()

        self.assertIsNotNone(dev._encode_cache.get(1, 7))   # rendered index
        self.assertIsNone(dev._encode_cache.get(0, 7))      # not the stale peek
        gen.compose_device_frame.assert_called_once_with("BASE")

    def test_display_device_keys_on_current_index(self):
        from thermalright_lcd_control.device_controller.display.display_device import (
            DisplayDevice,
        )
        from thermalright_lcd_control.device_controller.display.frame_cache import (
            FrameEncodeCache,
        )

        class _Dev(DisplayDevice):
            def get_header(self):
                return b""

            def send_packet(self, packet):
                pass

        gen = _straddle_gen()
        dev = _Dev.__new__(_Dev)
        dev._encode_cache = FrameEncodeCache()
        dev.header = b"H"
        dev._get_generator = lambda: gen
        dev._encode_image = lambda img: b"ENC"
        dev._prepare_frame_packets = lambda b: [b]
        dev.send_packet = lambda p: None

        dev._run()

        self.assertIsNotNone(dev._encode_cache.get(1, 7))   # rendered index
        self.assertIsNone(dev._encode_cache.get(0, 7))      # not the stale peek


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
