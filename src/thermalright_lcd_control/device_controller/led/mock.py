# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Config-driven mock LED device + capture sink. No USB."""
from __future__ import annotations

import struct

from .handshake import HandshakeResult, parse_handshake, synthetic_response
from .protocol import HEADER_SIZE
from .styles import STYLES, LedStyle


class CaptureSink:
    """Stands in for a real transport: records packets instead of USB."""

    def __init__(self) -> None:
        self.frames: list = []

    def send(self, payload: bytes) -> None:
        self.frames.append(bytes(payload))

    def decode_last(self) -> list:
        if not self.frames:
            return []
        pkt = self.frames[-1]
        length = struct.unpack_from("<H", pkt, 16)[0]
        body = pkt[HEADER_SIZE:HEADER_SIZE + length]
        return [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]


class MockLedDevice:
    def __init__(self, style: LedStyle) -> None:
        self._style = style
        self.sink = CaptureSink()
        self.style_info = STYLES[style]

    def handshake(self) -> HandshakeResult:
        return parse_handshake(synthetic_response(self._style))

    def send_packet(self, payload: bytes) -> None:
        self.sink.send(payload)
