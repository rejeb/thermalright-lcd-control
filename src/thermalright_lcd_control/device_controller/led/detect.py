# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""LED device auto-detection.

Scans USB for the registry's LED controllers (currently 0416:8001) and, for
each one physically present, resolves its hardware style via the HID
handshake (falling back to a disk-cached identity, then a default). Returns
device descriptors ready to surface as LED device tabs. When no LED device is
plugged in, returns an empty list.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from thermalright_lcd_control.common.supported_devices import led_supported_devices

from .handshake import ProbeCache, parse_handshake
from .protocol import REPORT_SIZE, build_init_packet
from .styles import LedStyle, resolve_pm

log = logging.getLogger(__name__)

_DEFAULT_STYLE = LedStyle.AX120
_PROBE_CACHE = Path.home() / ".thermalright" / "led_probe_cache.json"
_HANDSHAKE_SETTLE_S = 0.2
_READ_TIMEOUT_MS = 1000


def _is_present(vid: int, pid: int) -> bool:
    try:
        import usb.core
        return usb.core.find(idVendor=vid, idProduct=pid) is not None
    except Exception as e:   # pragma: no cover - libusb env-specific
        log.debug("LED presence check failed for %04x:%04x: %s", vid, pid, e)
        return False


def _handshake_style(vid: int, pid: int, cache: ProbeCache) -> LedStyle:
    """Open the LED device, run the HID handshake, resolve its style.

    The LED firmware answers the handshake only once per power cycle, so a
    successful result is cached and reused on later launches.
    """
    try:
        import hid
        dev = hid.Device(vid, pid)
        try:
            dev.write(b"\x00" + build_init_packet())
            time.sleep(_HANDSHAKE_SETTLE_S)
            resp = dev.read(REPORT_SIZE, _READ_TIMEOUT_MS)
            res = parse_handshake(bytes(resp))
            if res.style is not None:
                cache.save(vid, pid, res.pm, res.sub)
                log.info("LED %04x:%04x handshake -> style %s",
                         vid, pid, res.style.name)
                return res.style
            log.warning("LED %04x:%04x handshake: unknown PM=%d", vid, pid, res.pm)
        finally:
            dev.close()
    except Exception as e:
        log.warning("LED %04x:%04x handshake failed: %s", vid, pid, e)

    cached = cache.load(vid, pid)
    if cached is not None:
        style = resolve_pm(cached[0], cached[1]) or _DEFAULT_STYLE
        log.info("LED %04x:%04x using cached style %s", vid, pid, style.name)
        return style
    log.warning("LED %04x:%04x style unresolved — defaulting to %s",
                vid, pid, _DEFAULT_STYLE.name)
    return _DEFAULT_STYLE


def detect_led_devices() -> list[dict]:
    """Return descriptors for LED controllers currently plugged in."""
    cache = ProbeCache(_PROBE_CACHE)
    out: list[dict] = []
    for entry in led_supported_devices():
        vid, pid = entry["vid"], entry["pid"]
        if not _is_present(vid, pid):
            continue
        style = _handshake_style(vid, pid, cache)
        descriptor = dict(entry)
        descriptor["id"] = f"led_{vid:04x}_{pid:04x}"
        descriptor["style"] = style.name
        out.append(descriptor)
        log.info("Detected LED device %s (style %s)", descriptor["id"], style.name)
    return out
