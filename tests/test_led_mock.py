# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led import protocol as p
from thermalright_lcd_control.device_controller.led.mock import CaptureSink, MockLedDevice
from thermalright_lcd_control.device_controller.led.styles import LedStyle


def test_mock_handshake_resolves_style():
    dev = MockLedDevice(LedStyle.PA120)
    res = dev.handshake()
    assert res.style is LedStyle.PA120
    assert dev.style_info.style is LedStyle.PA120


def test_capture_sink_records_and_decodes():
    sink = CaptureSink()
    pkt = p.build_packet([(255, 0, 0)], None, [0])
    sink.send(pkt)
    assert len(sink.frames) == 1
    assert sink.decode_last() == [(102, 0, 0)]
