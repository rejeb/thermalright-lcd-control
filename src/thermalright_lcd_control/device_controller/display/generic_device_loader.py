# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Helpers to turn a ``devices.yaml`` entry into a data-driven
:class:`GenericDisplayDevice`. The orchestration (presence filtering, threads,
lifecycle) lives in the unified ``DeviceLoader``."""
from __future__ import annotations

from thermalright_lcd_control.device_controller.display.device_config import to_int
from thermalright_lcd_control.device_controller.display.generic_display_device import (
    DeviceDescriptor,
    GenericDisplayDevice,
)
from thermalright_lcd_control.device_controller.display.header import HeaderBuilder
from thermalright_lcd_control.device_controller.display.image_encoder import ImageEncoding
from thermalright_lcd_control.device_controller.display.transport import TransportType

_PLACEHOLDERS = ("width", "height", "payload_size", "cmd")


_as_int = to_int


def _parse_header_value(v):
    """A header value is a placeholder name, a bytes literal (hex str), or an int."""
    if isinstance(v, str):
        if v in _PLACEHOLDERS:
            return v
        return bytes.fromhex(v)
    return int(v)


def _build_header(spec: dict | None) -> HeaderBuilder:
    if not spec:
        return HeaderBuilder.static(b"")
    if "static" in spec:
        return HeaderBuilder.static(bytes.fromhex(spec["static"]))
    fmt = spec["format"]
    prefix = bytes.fromhex(spec.get("prefix", ""))
    values = [_parse_header_value(v) for v in spec.get("values", [])]
    return HeaderBuilder.from_struct(fmt, values, prefix)


def parse_descriptor(entry: dict) -> DeviceDescriptor:
    """Build a DeviceDescriptor from one YAML device entry."""
    if not entry.get("id"):
        raise ValueError(
            "devices.yaml entry is missing the mandatory 'id' field "
            f"(vid={entry.get('vid')}, pid={entry.get('pid')})")
    report_id = entry.get("report_id")
    return DeviceDescriptor(
        id=str(entry["id"]),
        vid=_as_int(entry["vid"]),
        pid=_as_int(entry["pid"]),
        width=int(entry["width"]),
        height=int(entry["height"]),
        transport=TransportType(entry["transport"]),
        chunk_size=_as_int(entry["chunk_size"]),
        encoding=ImageEncoding(entry["encoding"]),
        header=_build_header(entry.get("header")),
        report_id=bytes.fromhex(report_id) if report_id is not None else b"\x00",
        cmd=_as_int(entry.get("cmd", 0)),
        command=_as_int(entry.get("command", 0xF5)),
        jpeg_quality=int(entry.get("jpeg_quality", 85)),
        ep_in=_as_int(entry.get("ep_in", 0x81)),
        start_wait=float(entry.get("start_wait", 0.0)),
        generic=bool(entry.get("generic", True)),
    )


def build_generic_device(entry: dict, config_dir: str,
                         build_generator: bool = True) -> GenericDisplayDevice:
    """Build a data-driven device from one ``devices.yaml`` entry."""
    return GenericDisplayDevice(parse_descriptor(entry), config_dir)
