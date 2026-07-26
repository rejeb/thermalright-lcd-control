# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import struct

from thermalright_lcd_control.device_controller.led import protocol as p


def test_header_golden():
    h = p.build_header(3)
    assert len(h) == p.HEADER_SIZE
    assert h[0:4] == bytes([0xDA, 0xDB, 0xDC, 0xDD])
    assert h[12] == p.CMD_DATA
    assert struct.unpack_from("<H", h, 16)[0] == 3


def test_scale_applies_0_4_and_off_mask():
    out = p.scale_colors([(255, 100, 0), (255, 255, 255)], [True, False])
    assert out[0] == (102, 40, 0)   # int(255*0.4)=102, int(100*0.4)=40
    assert out[1] == (0, 0, 0)      # off -> black


def test_remap_reorders():
    colors = [(1, 1, 1), (2, 2, 2), (3, 3, 3)]
    assert p.remap_colors(colors, [2, 0, 1]) == [(3, 3, 3), (1, 1, 1), (2, 2, 2)]


def test_build_packet_length_and_body():
    colors = [(255, 0, 0)]
    pkt = p.build_packet(colors, None, [0])
    assert pkt[0:4] == p.MAGIC
    assert struct.unpack_from("<H", pkt, 16)[0] == 3   # 1 led * 3 bytes
    assert pkt[p.HEADER_SIZE:p.HEADER_SIZE + 3] == bytes([102, 0, 0])
