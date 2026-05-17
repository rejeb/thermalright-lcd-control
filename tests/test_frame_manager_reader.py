# SPDX-License-Identifier: Apache-2.0
import pytest
import pyvips

from thermalright_lcd_control.device_controller.display import vips_utils as vu
from thermalright_lcd_control.device_controller.display.config import BackgroundType
from thermalright_lcd_control.device_controller.display.frame_manager import FrameManager


class Cfg:
    def __init__(self, path, bg_type, media_endpoint=None):
        self.background_path = str(path)
        self.background_type = bg_type
        self.metrics_configs = []
        self.media_endpoint = media_endpoint


def _make_image(tmp_path, name="bg.png", rgb=(255, 0, 0), size=(32, 24)):
    p = tmp_path / name
    vu.to_rgb(vu.solid(*size, (*rgb, 255))).write_to_file(str(p))
    return p


def _make_gif(path, sizes_rgb, delays_ms, w=16, h=16):
    pages = [vu.to_rgb(vu.solid(w, h, (*rgb, 255))) for rgb in sizes_rgb]
    anim = pages[0]
    for pg in pages[1:]:
        anim = anim.join(pg, "vertical")
    anim = anim.copy()
    anim.set_type(pyvips.GValue.gint_type, "page-height", h)
    anim.set_type(pyvips.GValue.array_int_type, "delay", delays_ms)
    anim.write_to_file(str(path))


def test_static_image_single_tuple(tmp_path):
    fm = FrameManager(Cfg(_make_image(tmp_path), BackgroundType.IMAGE))
    frames = fm.read_frames()
    assert len(frames) == 1
    frame, delay = frames[0]
    assert (frame.width, frame.height) == (32, 24)
    assert frame.bands == 4
    assert delay == FrameManager.DEFAULT_FRAME_DURATION


def test_gif_returns_per_frame_delays(tmp_path):
    p = tmp_path / "bg.gif"
    _make_gif(p, [(255, 0, 0), (0, 0, 255)], [100, 250])
    frames = FrameManager(Cfg(p, BackgroundType.GIF)).read_frames()
    assert len(frames) == 2
    assert [round(d, 2) for _, d in frames] == [0.1, 0.25]
    assert all(f.bands == 4 and (f.width, f.height) == (16, 16) for f, _ in frames)


def test_reader_holds_no_frame_references(tmp_path):
    fm = FrameManager(Cfg(_make_image(tmp_path), BackgroundType.IMAGE))
    fm.read_frames()
    held = [v for v in vars(fm).values()
            if isinstance(v, pyvips.Image)
            or (isinstance(v, list) and any(isinstance(x, (pyvips.Image, tuple)) for x in v))]
    assert held == []


def test_video_reads_all_frames(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    p = tmp_path / "bg.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 10, (8, 6))
    for i in range(10):
        w.write(np.full((6, 8, 3), i * 20, dtype=np.uint8))
    w.release()
    frames = FrameManager(Cfg(p, BackgroundType.VIDEO)).read_frames()
    assert len(frames) == 10
    assert all((f.width, f.height) == (8, 6) for f, _ in frames)
    assert all(d == pytest.approx(1 / 10) for _, d in frames)


def test_collection_reads_sorted_images(tmp_path):
    d = tmp_path / "col"
    d.mkdir()
    for i in range(3):
        _make_image(d.parent, name=f"col/{i}.png", rgb=(i * 50, 0, 0), size=(8, 6))
    frames = FrameManager(Cfg(d, BackgroundType.IMAGE_COLLECTION)).read_frames()
    assert len(frames) == 3
    assert [vu.to_numpy(f)[0, 0, 0] for f, _ in frames] == [0, 50, 100]


def test_iter_frames_is_lazy_for_video(tmp_path):
    """Videos stream frame-by-frame so the caller can compress each frame
    before the next raw one is decoded (peak = 1 frame, not the clip)."""
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    p = tmp_path / "bg.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 10, (8, 6))
    for i in range(5):
        w.write(np.full((6, 8, 3), i * 20, dtype=np.uint8))
    w.release()
    it = FrameManager(Cfg(p, BackgroundType.VIDEO)).iter_frames()
    frame, delay = next(it)          # first frame without exhausting the clip
    assert (frame.width, frame.height) == (8, 6)
    assert len(list(it)) == 4


def test_missing_media_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        FrameManager(Cfg(tmp_path / "nope.png", BackgroundType.IMAGE)).read_frames()


def test_missing_video_is_downloaded_before_read(tmp_path, monkeypatch):
    """A missing bundled video is fetched on-demand by FrameManager itself
    (the single read choke point) before decoding — so any config path that
    references it (rotation swap, engine reload) self-heals without every
    caller having to pre-download."""
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    res = tmp_path / "240320"
    res.mkdir()
    dest = res / "clip.mp4"

    calls = []

    def _fake_ensure(path, media_endpoint=None):
        calls.append((str(path), media_endpoint))
        w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (8, 6))
        for i in range(3):
            w.write(np.full((6, 8, 3), i * 20, dtype=np.uint8))
        w.release()

    monkeypatch.setattr(
        "thermalright_lcd_control.device_controller.display.asset_download."
        "ensure_background_downloaded", _fake_ensure)

    fm = FrameManager(Cfg(dest, BackgroundType.VIDEO,
                          media_endpoint="https://example.test/tr/"))
    frames = fm.read_frames()

    assert calls == [(str(dest), "https://example.test/tr/")]
    assert len(frames) == 3
