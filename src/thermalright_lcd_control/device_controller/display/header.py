# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Header construction: a static header, or a struct-packed header with
per-frame placeholders (width / height / payload_size / cmd)."""
import struct
from collections.abc import Sequence

_PLACEHOLDERS = ("width", "height", "payload_size", "cmd")


class HeaderBuilder:
    """Builds a device frame header.

    Use ``HeaderBuilder.static(bytes)`` for a fixed header, or
    ``HeaderBuilder.from_struct(fmt, values, prefix)`` when some fields depend
    on the frame (resolve via the placeholders width/height/payload_size/cmd).
    """

    def build(self, width: int = 0, height: int = 0, payload_size: int = 0,
              cmd: int = 0) -> bytes:
        raise NotImplementedError

    @staticmethod
    def static(header: bytes) -> "HeaderBuilder":
        return _StaticHeader(bytes(header))

    @staticmethod
    def from_struct(fmt: str, values: Sequence, prefix: bytes = b"") -> "HeaderBuilder":
        return _StructHeader(fmt, tuple(values), bytes(prefix))


class _StaticHeader(HeaderBuilder):
    def __init__(self, header: bytes):
        self._header = header

    def build(self, width: int = 0, height: int = 0, payload_size: int = 0,
              cmd: int = 0) -> bytes:
        return self._header


class _StructHeader(HeaderBuilder):
    """struct.pack-based header. Each entry of ``values`` is either a literal
    (int / bytes) passed through, or a placeholder name (str) resolved per
    frame. ``fmt`` may use ``x`` pad bytes for gaps (e.g. ChiZhu 64-byte header)."""

    def __init__(self, fmt: str, values: tuple, prefix: bytes = b""):
        self.fmt = fmt
        self.values = values
        self.prefix = prefix

    def build(self, width: int = 0, height: int = 0, payload_size: int = 0,
              cmd: int = 0) -> bytes:
        ctx = {"width": width, "height": height, "payload_size": payload_size, "cmd": cmd}
        resolved = []
        for v in self.values:
            if isinstance(v, str):
                if v not in ctx:
                    raise ValueError(
                        f"Unknown header placeholder {v!r}; expected one of {_PLACEHOLDERS}"
                    )
                resolved.append(ctx[v])
            else:
                resolved.append(v)
        return self.prefix + struct.pack(self.fmt, *resolved)
