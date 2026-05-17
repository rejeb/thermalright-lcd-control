# SPDX-License-Identifier: Apache-2.0
import threading
import unittest
from unittest import mock

from thermalright_lcd_control.device_controller.display import vips_utils as vu

from thermalright_lcd_control.device_controller.display.event_bus import EventBus, Topic
from thermalright_lcd_control.device_controller.display.render_engine import RenderEngine


def _mk_cfg(bg="cur.mp4", fg=None, alpha=1.0, rotation=0, metrics=()):
    c = mock.MagicMock()
    c.background_path = bg
    c.background_type = "video"
    c.foreground_image_path = fg
    c.foreground_position = (0, 0)
    c.foreground_alpha = alpha
    c.rotation = rotation
    c.metrics_configs = list(metrics)
    return c


def _fake_generator(version=7, bg="cur.mp4"):
    gen = mock.MagicMock()
    gen.get_base_frame.return_value = vu.to_rgb(vu.solid(4, 2, (1, 2, 3, 255)))
    gen.compose_device_frame.return_value = vu.to_rgb(vu.solid(4, 2, (4, 5, 6, 255)))
    gen._overlay_version = version
    gen.sync_overlay.return_value = version
    gen.config = _mk_cfg(bg)
    gen.peek_next_frame_idx.return_value = 0
    # After get_base_frame() advances timing, current_frame_index is the frame
    # ``base`` holds — the engine keys the encode cache on it (not peek).
    gen.current_frame_index = 0
    gen.frame_duration = 0.0
    gen.frame_count = 2
    gen.media_resident = True
    return gen


class _FakeSink:
    def __init__(self):
        self.calls = []

    def send_image(self, img, frame_idx, overlay_version):
        self.calls.append((frame_idx, overlay_version))


class _CachingSink:
    """Sink exposing ``resend`` (the GenericDisplayDevice contract)."""

    def __init__(self, cached):
        self._cached = set(cached)
        self.resent = []
        self.sent = []

    def resend(self, frame_idx, overlay_version):
        if (frame_idx, overlay_version) in self._cached:
            self.resent.append((frame_idx, overlay_version))
            return True
        return False

    def send_image(self, img, frame_idx, overlay_version):
        self.sent.append((frame_idx, overlay_version))


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
    # By default a reload resolves to a DIFFERENT background → full rebuild path.
    eng._build_config = mock.MagicMock(return_value=_mk_cfg(bg="new.mp4"))
    return eng


def _patch_replace(new_gen=None):
    return mock.patch(
        "thermalright_lcd_control.device_controller.display.render_engine."
        "DisplayGenerator.replace",
        return_value=new_gen or _fake_generator(version=99, bg="new.mp4"))


class TestRenderEngine(unittest.TestCase):
    def test_tick_reads_base_frame(self):
        gen = _fake_generator()
        eng = _engine(gen=gen)
        eng._tick()
        gen.get_base_frame.assert_called_once()

    def test_build_config_forwards_media_endpoint(self):
        # The configured host must reach ConfigLoader (→ DisplayConfig →
        # FrameManager) so a video the GUI never pre-downloaded is fetched from
        # the right endpoint instead of the public default.
        eng = RenderEngine.__new__(RenderEngine)
        eng.width, eng.height = 320, 240
        eng.config_file = "/cfg/config_dev1.yaml"
        eng.media_endpoint = "http://host.test/tr"
        with mock.patch(
            "thermalright_lcd_control.device_controller.display.render_engine.ConfigLoader"
        ) as CL:
            loader = CL.return_value
            eng._build_config({"display": {"x": 1}})
            loader.load_config_from_dict.assert_called_once_with(
                {"display": {"x": 1}}, 320, 240, media_endpoint="http://host.test/tr")
            eng._build_config(None)
            loader.load_config.assert_called_once_with(
                "/cfg/config_dev1.yaml", 320, 240, media_endpoint="http://host.test/tr")

    def test_tick_drives_sink_when_present(self):
        sink = _FakeSink()
        eng = _engine(sink=sink)
        eng._tick()
        self.assertEqual(sink.calls, [(0, 7)])  # (frame_idx, overlay_version)

    def test_tick_skips_compose_on_cache_hit(self):
        gen = _fake_generator(version=7)
        sink = _CachingSink(cached={(0, 7)})
        eng = _engine(sink=sink, gen=gen)
        eng._tick()
        gen.compose_device_frame.assert_not_called()   # CPU-1: no recomposite
        self.assertEqual(sink.resent, [(0, 7)])
        self.assertEqual(sink.sent, [])

    def test_tick_composes_on_cache_miss(self):
        gen = _fake_generator(version=7)
        sink = _CachingSink(cached=set())
        eng = _engine(sink=sink, gen=gen)
        eng._tick()
        gen.compose_device_frame.assert_called_once()
        self.assertEqual(sink.sent, [(0, 7)])

    def test_tick_without_sink_only_reads_base(self):
        gen = _fake_generator()
        eng = _engine(sink=None, gen=gen)
        eng._tick()
        gen.compose_device_frame.assert_not_called()
        gen.get_base_frame.assert_called_once()

    def test_matching_reload_rebuilds_with_inmemory_config(self):
        eng = _engine()
        bus = EventBus()
        bus.subscribe(Topic.CONFIG_RELOAD, eng._on_config_reload)
        bus.publish(Topic.CONFIG_RELOAD, "dev1", {"display": {"x": 1}})
        self.assertTrue(eng._reload_requested.is_set())
        self.assertEqual(eng._pending_config, {"display": {"x": 1}})
        with _patch_replace() as replace:
            eng._tick()  # reload happens at the top of the tick
        eng._build_config.assert_called_once_with({"display": {"x": 1}})
        replace.assert_called_once()  # different bg → rebuild

    def test_non_matching_reload_ignored(self):
        eng = _engine()
        eng._on_config_reload("other", {"display": {}})
        self.assertFalse(eng._reload_requested.is_set())

    def test_reload_invalidates_sink_cache(self):
        sink = mock.MagicMock()
        eng = _engine(sink=sink)
        eng._reload_requested.set()
        eng._pending_config = {"display": {}}
        with _patch_replace():
            eng._tick()
        sink.invalidate_cache.assert_called_once()

    def test_tick_without_reload_does_not_invalidate_sink(self):
        sink = mock.MagicMock()
        eng = _engine(sink=sink)
        eng._tick()
        sink.invalidate_cache.assert_not_called()


class TestRenderEngineRefresh(unittest.TestCase):
    def _engine(self, sink=None):
        eng = _engine(sink=sink)
        eng._generator.config = _mk_cfg(bg="a.mp4")
        return eng

    def test_overlay_only_change_refreshes_in_place(self):
        eng = self._engine()
        eng._build_config = mock.MagicMock(
            return_value=_mk_cfg(bg="a.mp4", metrics=[object()]))
        eng._reload_requested.set()
        eng._pending_config = {"display": {}}
        eng._get_generator()
        eng._generator.refresh_overlay.assert_called_once()   # no rebuild

    def test_media_change_rebuilds(self):
        eng = self._engine()
        eng._build_config = mock.MagicMock(return_value=_mk_cfg(bg="OTHER.mp4"))
        eng._reload_requested.set()
        eng._pending_config = {"display": {}}
        with _patch_replace() as replace:
            eng._get_generator()
        replace.assert_called_once()  # full rebuild

    def test_rotation_change_is_overlay_only(self):
        # Rotation is applied at compose time → overlay-level change, no rebuild.
        eng = self._engine()
        eng._build_config = mock.MagicMock(return_value=_mk_cfg(bg="a.mp4", rotation=90))
        eng._reload_requested.set()
        eng._pending_config = {"display": {}}
        eng._get_generator()
        eng._generator.refresh_overlay.assert_called_once()

    def test_sink_gets_frame_count(self):
        sink = mock.MagicMock()
        eng = self._engine(sink=sink)
        eng._build_config = mock.MagicMock(
            return_value=_mk_cfg(bg="a.mp4", metrics=[object()]))
        eng._reload_requested.set()
        eng._get_generator()
        sink.set_frame_count.assert_called_with(2)


if __name__ == "__main__":
    unittest.main()
