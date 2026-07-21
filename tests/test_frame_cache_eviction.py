# SPDX-License-Identifier: Apache-2.0
"""FrameEncodeCache must not retain encoded frames of older overlay versions:
only the current version is ever re-sent, so a version bump makes every older
entry dead weight (up to hundreds of MB for an RGB565 clip)."""
from thermalright_lcd_control.device_controller.display.frame_cache import FrameEncodeCache


def test_version_bump_evicts_older_versions_eagerly():
    c = FrameEncodeCache()
    c.set_frame_count(10)
    for i in range(10):
        c.store(i, 0, b"v0")
    assert len(c) == 10
    c.store(0, 1, b"v1")            # first frame of the new overlay version
    assert c.get(0, 1) == b"v1"
    assert c.get(1, 0) is None      # old version gone immediately
    assert len(c) == 1


def test_limit_tracks_clip_size_not_640_floor():
    c = FrameEncodeCache()
    c.set_frame_count(3)            # static-ish clip: no 640-entry floor
    assert c._limit <= 8


def test_same_version_entries_kept_up_to_clip():
    c = FrameEncodeCache()
    c.set_frame_count(5)
    for i in range(5):
        c.store(i, 7, bytes([i]))
    assert all(c.get(i, 7) == bytes([i]) for i in range(5))
