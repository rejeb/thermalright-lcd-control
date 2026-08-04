# SPDX-License-Identifier: Apache-2.0
"""FrameEncodeCache holds at most one clip of encoded frames.

Entries are keyed on frame index alone. A metrics change no longer creates a new
overlay-version dimension: RenderEngine re-encodes every frame in place from its
background pass, so stale and fresh entries never coexist. The bound therefore
only has to track the clip length, which keeps an RGB565 clip from growing into
hundreds of MB.
"""
from thermalright_lcd_control.device_controller.display.frame_cache import FrameEncodeCache


def test_reencoding_a_frame_replaces_it_in_place():
    c = FrameEncodeCache()
    c.set_frame_count(10)
    for i in range(10):
        c.store(i, b"v0")
    assert len(c) == 10

    c.store(0, b"v1")               # same frame, freshly encoded overlay
    assert c.get(0) == b"v1"        # replaced, not duplicated
    assert len(c) == 10


def test_limit_tracks_clip_size_not_640_floor():
    c = FrameEncodeCache()
    c.set_frame_count(3)            # static-ish clip: no 640-entry floor
    assert c._limit <= 8


def test_whole_clip_is_retained():
    c = FrameEncodeCache()
    c.set_frame_count(5)
    for i in range(5):
        c.store(i, bytes([i]))
    assert all(c.get(i) == bytes([i]) for i in range(5))


def test_store_beyond_the_limit_evicts_the_oldest_entry():
    c = FrameEncodeCache()
    c.set_frame_count(2)            # limit = 4
    for i in range(5):
        c.store(i, bytes([i]))
    assert len(c) == 4
    assert c.get(0) is None         # oldest evicted
    assert c.get(4) == bytes([4])


def test_clear_drops_everything():
    c = FrameEncodeCache()
    c.set_frame_count(3)
    c.store(0, b"x")
    c.clear()
    assert len(c) == 0
    assert c.get(0) is None
