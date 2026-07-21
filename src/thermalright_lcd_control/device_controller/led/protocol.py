# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""LED wire protocol: header + body packet building. Pure logic."""
from __future__ import annotations

import struct

MAGIC = bytes([0xDA, 0xDB, 0xDC, 0xDD])
HEADER_SIZE = 20
REPORT_SIZE = 64
COLOR_SCALE = 0.4
CMD_INIT = 1
CMD_DATA = 2


def build_header(payload_len: int) -> bytes:
    h = bytearray(HEADER_SIZE)
    h[0:4] = MAGIC
    h[12] = CMD_DATA
    struct.pack_into("<H", h, 16, payload_len)
    return bytes(h)


def remap_colors(colors: list, wire_remap: list) -> list:
    if not wire_remap or len(wire_remap) != len(colors):
        return list(colors)
    return [colors[i] for i in wire_remap]


def _clamp(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def scale_colors(colors: list, is_on: "list | None") -> list:
    out = []
    for i, (r, g, b) in enumerate(colors):
        on = True if is_on is None else is_on[i]
        if on:
            out.append((_clamp(int(r * COLOR_SCALE)),
                        _clamp(int(g * COLOR_SCALE)),
                        _clamp(int(b * COLOR_SCALE))))
        else:
            out.append((0, 0, 0))
    return out


def build_packet(colors: list, is_on: "list | None", wire_remap: list) -> bytes:
    remapped = remap_colors(colors, wire_remap)
    remapped_on = remap_colors(list(is_on), wire_remap) if is_on is not None else None
    scaled = scale_colors(remapped, remapped_on)
    body = bytearray(len(scaled) * 3)
    for i, (r, g, b) in enumerate(scaled):
        body[i * 3] = r
        body[i * 3 + 1] = g
        body[i * 3 + 2] = b
    return build_header(len(body)) + bytes(body)


def build_init_packet() -> bytes:
    h = bytearray(REPORT_SIZE)
    h[0:4] = MAGIC
    h[12] = CMD_INIT
    return bytes(h)


def chunk_reports(packet: bytes, report_id: int = 0) -> list:
    """Split into REPORT_SIZE reports, each prefixed with report_id byte."""
    reports = []
    for i in range(0, len(packet), REPORT_SIZE):
        chunk = packet[i:i + REPORT_SIZE]
        if len(chunk) < REPORT_SIZE:
            chunk = chunk + b"\x00" * (REPORT_SIZE - len(chunk))
        reports.append(bytes([report_id]) + chunk)
    return reports
