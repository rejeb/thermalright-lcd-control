# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.handshake import (
    ProbeCache,
    parse_handshake,
    synthetic_response,
)
from thermalright_lcd_control.device_controller.led.styles import LedStyle


def test_synthetic_roundtrip():
    resp = synthetic_response(LedStyle.PA120)
    res = parse_handshake(resp)
    assert res.style is LedStyle.PA120
    assert res.pm == 51


def test_parse_unknown_pm_style_none():
    resp = bytearray(64)
    resp[0:4] = bytes([0xDA, 0xDB, 0xDC, 0xDD])
    resp[5] = 0xEE
    res = parse_handshake(bytes(resp))
    assert res.style is None
    assert res.pm == 0xEE


def test_probe_cache_roundtrip(tmp_path):
    cache = ProbeCache(tmp_path / "probe.json")
    cache.save(0x0416, 0x8001, 51, 0)
    assert cache.load(0x0416, 0x8001) == (51, 0)
    assert cache.load(0x0416, 0x9999) is None
