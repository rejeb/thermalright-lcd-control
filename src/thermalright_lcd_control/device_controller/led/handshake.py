# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""LED handshake parsing + probe cache. Pure logic (cache does file IO)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .protocol import MAGIC, REPORT_SIZE
from .styles import LedStyle, PM_TO_STYLE, resolve_pm


@dataclass
class HandshakeResult:
    pm: int
    sub: int
    style: "LedStyle | None"


def parse_handshake(resp: bytes) -> HandshakeResult:
    if len(resp) < 7:
        return HandshakeResult(pm=0, sub=0, style=None)
    pm = resp[5]
    sub = resp[4]
    return HandshakeResult(pm=pm, sub=sub, style=resolve_pm(pm, sub))


def synthetic_response(style: LedStyle) -> bytes:
    """Build a fake 64-byte handshake yielding this style's PM/SUB."""
    pm = next(k for k, v in PM_TO_STYLE.items() if v is style)
    resp = bytearray(REPORT_SIZE)
    resp[0:4] = MAGIC
    resp[4] = 0            # sub
    resp[5] = pm
    resp[12] = 1           # init cmd echo
    return bytes(resp)


class ProbeCache:
    def __init__(self, path) -> None:
        self._path = Path(path)

    def _key(self, vid: int, pid: int) -> str:
        return f"{vid:04x}_{pid:04x}"

    def save(self, vid: int, pid: int, pm: int, sub: int) -> None:
        data = {}
        if self._path.is_file():
            try:
                data = json.loads(self._path.read_text())
            except (OSError, ValueError):
                data = {}
        data[self._key(vid, pid)] = {"pm": pm, "sub": sub}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def load(self, vid: int, pid: int):
        if not self._path.is_file():
            return None
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return None
        entry = data.get(self._key(vid, pid))
        if entry is None:
            return None
        return (entry["pm"], entry["sub"])
