# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Handshake-based device probing: ask connected hardware for its screen.

Each supported wire family answers a fixed init packet with a response
carrying PM/SUB (or FBL) bytes. ``pm_to_fbl`` + ``screen_for`` map those to
(width, height, encoding). Tables and wire constants follow the Windows TRCC
convention (via the trcc-linux project, core/protocol.py + adapters/device/).

Pure logic (tables + parsers) is separated from I/O (probe runners keyed by
family name in ``PROBE_FAMILIES``) so everything except the actual USB
round-trip is unit-testable. Which family a VID:PID speaks is registry data
(see probe_registry.py), not code.
"""
from __future__ import annotations

import logging
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass

import usb.core
import usb.util

from thermalright_lcd_control.device_controller.display.image_encoder import ImageEncoding
from thermalright_lcd_control.device_controller.display.transport import TransportType

logger = logging.getLogger(__name__)


class ProbeError(RuntimeError):
    """Probe failed: device absent, busy, or answered garbage."""


@dataclass(frozen=True)
class ProbeResult:
    """What the hardware reported about itself."""
    transport: TransportType
    width: int
    height: int
    encoding: ImageEncoding
    pm: int = 0
    sub: int = 0
    fbl: int = 0


# --- screen tables (TRCC FBL/PM convention) -----------------------------------

# FBL → (width, height, jpeg, big_endian)
_FBL_SCREENS: dict[int, tuple[int, int, bool, bool]] = {
    36: (240, 240, False, False),
    37: (240, 240, False, False),
    50: (320, 240, False, False),
    51: (320, 240, False, False),
    52: (320, 240, False, False),
    53: (320, 240, False, False),
    54: (360, 360, True, False),
    58: (320, 240, False, False),
    64: (640, 480, False, False),
    72: (480, 480, False, False),
    100: (320, 320, False, True),
    101: (320, 320, False, True),
    102: (320, 320, False, True),
    114: (1600, 720, True, False),
    128: (1280, 480, True, False),
    129: (480, 480, False, False),
    192: (1920, 462, True, False),
    224: (854, 480, True, False),
}

# PM → FBL where PM != FBL (all other PMs: PM == FBL, the SCSI poll convention).
_PM_TO_FBL_OVERRIDES: dict[int, int] = {
    5: 50, 7: 64, 9: 224, 10: 224, 11: 224, 12: 224, 13: 224, 14: 64,
    15: 224, 16: 224, 17: 224, 32: 100, 50: 50, 63: 114, 64: 114,
    65: 192, 66: 192, 68: 192, 69: 192,
}

# FBL 224/192 are shared by several resolutions; the PM byte disambiguates.
_FBL_224_BY_PM: dict[int, tuple[int, int]] = {
    10: (960, 540), 12: (800, 480), 13: (960, 320),
    15: (640, 172), 16: (960, 540), 17: (960, 320),
}
_FBL_192_BY_PM: dict[int, tuple[int, int]] = {
    68: (1280, 480), 69: (1920, 440),
}

# (PM, SUB) pairs where the sub byte changes the FBL mapping.
_PM_SUB_TO_FBL: dict[tuple[int, int], int] = {
    (1, 48): 114,
    (1, 49): 192,
}


def pm_to_fbl(pm: int, sub: int = 0) -> int:
    """Map a handshake PM byte to an FBL code (PM == FBL unless overridden)."""
    if (pm, sub) in _PM_SUB_TO_FBL:
        return _PM_SUB_TO_FBL[(pm, sub)]
    return _PM_TO_FBL_OVERRIDES.get(pm, pm)


def screen_for(fbl: int, pm: int = 0) -> tuple[int, int, bool, bool] | None:
    """(width, height, jpeg, big_endian) for an FBL code, or None if unknown."""
    base = _FBL_SCREENS.get(fbl)
    if base is None:
        return None
    w, h, jpeg, be = base
    if fbl == 224:
        w, h = _FBL_224_BY_PM.get(pm, (854, 480))
    elif fbl == 192:
        w, h = _FBL_192_BY_PM.get(pm, (1920, 462))
    return (w, h, jpeg, be)


# --- response parsers (pure) ---------------------------------------------------

_T2_MAGIC = bytes([0xDA, 0xDB, 0xDC, 0xDD])

# Bulk devices that USBLCDNew recognises; anything else clamps to 480x480.
_BULK_KNOWN_PMS = frozenset(
    {5, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 32, 50, 63, 64, 65, 66, 68, 69})
_BULK_BASE_FBL = 72


def _screen_or_raise(fbl: int, pm: int) -> tuple[int, int, bool, bool]:
    screen = screen_for(fbl, pm)
    if screen is None:
        raise ProbeError(f"device reported unknown screen code FBL={fbl} (PM={pm})")
    return screen


def parse_bulk_response(resp: bytes) -> ProbeResult:
    """USBLCDNew bulk handshake: PM at resp[24], SUB at resp[36]."""
    if len(resp) < 41 or resp[24] == 0:
        raise ProbeError("invalid bulk handshake response")
    pm, sub = resp[24], resp[36]
    if pm in _BULK_KNOWN_PMS or (pm == 1 and sub in (48, 49)):
        fbl = pm_to_fbl(pm, sub)
    else:
        fbl = _BULK_BASE_FBL
    w, h, _, _ = _screen_or_raise(fbl, pm)
    # USBLCDNew uses JPEG (cmd=2) for every PM except 32 (raw RGB565, cmd=3).
    enc = ImageEncoding.RGB565_BE if pm == 32 else ImageEncoding.JPEG
    return ProbeResult(TransportType.USB_BULK, w, h, enc, pm, sub, fbl)


def parse_hid_t2_response(resp: bytes) -> ProbeResult:
    """HID type 2 (DA DB DC DD): PM at resp[5], SUB at resp[4]."""
    if len(resp) < 20 or bytes(resp[0:4]) != _T2_MAGIC or resp[12] != 0x01:
        raise ProbeError("invalid HID type-2 handshake response")
    pm, sub = resp[5], resp[4]
    fbl = pm_to_fbl(pm, sub)
    w, h, jpeg, _ = _screen_or_raise(fbl, pm)
    enc = ImageEncoding.JPEG if jpeg else ImageEncoding.RGB565_LE_COLUMNS
    return ProbeResult(TransportType.HID, w, h, enc, pm, sub, fbl)


def parse_hid_t3_response(resp: bytes) -> ProbeResult:
    """HID type 3 (F5 prefix): FBL = resp[0] - 1 (0x65→100, 0x66→101)."""
    if len(resp) < 14 or resp[0] not in (0x65, 0x66):
        raise ProbeError("invalid HID type-3 handshake response")
    fbl = resp[0] - 1
    w, h, jpeg, _ = _screen_or_raise(fbl, fbl)
    enc = ImageEncoding.JPEG if jpeg else ImageEncoding.RGB565_LE_COLUMNS
    return ProbeResult(TransportType.HID, w, h, enc, fbl, 0, fbl)


def parse_ly_response(resp: bytes, pid: int) -> ProbeResult:
    """LY handshake: PM = 64 + resp[20] (0x5408) or 50 + resp[36] (0x5409).

    resp[8] is 1 per TRCC, but real Trofeo Vision 9.16 firmware answers 2
    (matches LyTransport, which soft-warns on the same byte) — accept both.
    """
    if len(resp) < 37 or resp[0] != 3 or resp[1] != 0xFF or resp[8] not in (1, 2):
        raise ProbeError("invalid LY handshake response")
    if pid == 0x5408:
        raw = resp[20]
        if raw <= 3:
            raw = 1
        pm, sub = 64 + raw, resp[22] + 1
    else:
        pm, sub = 50 + resp[36], resp[22]
    fbl = pm_to_fbl(pm, sub)
    w, h, jpeg, _ = _screen_or_raise(fbl, pm)
    enc = ImageEncoding.JPEG if jpeg else ImageEncoding.RGB565_BE
    return ProbeResult(TransportType.USB_BULK_LY, w, h, enc, pm, sub, fbl)


def parse_scsi_poll(resp: bytes) -> ProbeResult:
    """SCSI poll: FBL is the first response byte (PM == FBL convention)."""
    if not resp:
        raise ProbeError("empty SCSI poll response")
    fbl = resp[0]
    w, h, jpeg, _ = _screen_or_raise(fbl, fbl)
    enc = ImageEncoding.JPEG if jpeg else ImageEncoding.RGB565_BE
    return ProbeResult(TransportType.SCSI, w, h, enc, fbl, 0, fbl)


# --- I/O runners ----------------------------------------------------------------

_TIMEOUT_MS = 2000
_SCSI_POLL_SIZE = 0xE100
_SCSI_BOOT_SIGNATURE = b"\xa1\xa2\xa3\xa4"
_SCSI_BOOT_RETRIES = 2
_SCSI_BOOT_WAIT_S = 1.0
_EBUSY = 16

# Init packets (TRCC wire constants).
_BULK_HANDSHAKE = (bytes([0x12, 0x34, 0x56, 0x78]) + bytes(52)
                   + b"\x01" + bytes(7))                       # 64 bytes, 1 @ [56]
_T2_INIT = (_T2_MAGIC + bytes(8) + b"\x01\x00\x00\x00").ljust(512, b"\x00")
_T3_INIT = (bytes([0xF5, 0x00, 0x01, 0x00, 0xBC, 0xFF, 0xB6, 0xC8])
            + bytes(4) + b"\x00\x04\x00\x00" + bytes(1024))    # 1040 bytes


def _find_bulk_eps(dev) -> tuple[int, int, int]:
    """(interface, ep_out, ep_in) — prefer vendor-specific interfaces."""
    dev.set_configuration()
    cfg = dev.get_active_configuration()
    candidates = sorted(cfg, key=lambda i: i.bInterfaceClass != 255)
    for intf in candidates:
        ep_out = ep_in = None
        for ep in intf:
            if usb.util.endpoint_type(ep.bmAttributes) != usb.util.ENDPOINT_TYPE_BULK:
                continue
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                ep_out = ep_out if ep_out is not None else ep.bEndpointAddress
            else:
                ep_in = ep_in if ep_in is not None else ep.bEndpointAddress
        if ep_out is not None and ep_in is not None:
            return intf.bInterfaceNumber, ep_out, ep_in
    raise ProbeError("no bulk IN/OUT endpoint pair found")


def _open_usb(vid: int, pid: int):
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        raise ProbeError(f"device {vid:04x}:{pid:04x} not connected")
    try:
        for intf in dev.get_active_configuration():
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)
    except (NotImplementedError, usb.core.USBError) as e:
        logger.debug(f"probe: could not detach kernel driver: {e}")
    return dev


def _run_usb_bulk(vid: int, pid: int, payload: bytes, read_size: int, parse):
    """Open raw USB, write the init payload, read + parse the response."""
    dev = _open_usb(vid, pid)
    iface = None
    try:
        iface, ep_out, ep_in = _find_bulk_eps(dev)
        usb.util.claim_interface(dev, iface)
        dev.write(ep_out, payload, timeout=_TIMEOUT_MS)
        resp = bytes(dev.read(ep_in, read_size, timeout=_TIMEOUT_MS))
        return parse(resp)
    except usb.core.USBError as e:
        if e.errno == _EBUSY:
            raise ProbeError(
                "device is in use (service running?) — stop it or replug") from e
        raise ProbeError(f"USB probe failed: {e}") from e
    finally:
        if iface is not None:
            try:
                usb.util.release_interface(dev, iface)
            except Exception:
                pass
        usb.util.dispose_resources(dev)


def _run_hid(vid: int, pid: int, init: bytes, read_size: int, parse):
    """Probe over hidapi (report id 0x00 + init payload, then a timed read)."""
    import hid
    try:
        dev = hid.Device(vid, pid)
    except Exception as e:
        raise ProbeError(f"cannot open HID device {vid:04x}:{pid:04x}: {e}") from e
    try:
        dev.write(b"\x00" + init)
        resp = bytes(dev.read(read_size, _TIMEOUT_MS))
        return parse(resp)
    except ProbeError:
        raise
    except Exception as e:
        raise ProbeError(f"HID probe failed: {e}") from e
    finally:
        dev.close()


def _run_scsi_poll(vid: int, pid: int):
    """BOT data-IN poll: CBW(flag 0x80) + CDB[F5 .. size] → FBL byte."""
    dev = _open_usb(vid, pid)
    iface = None
    try:
        iface, ep_out, ep_in = _find_bulk_eps(dev)
        usb.util.claim_interface(dev, iface)
        cdb = struct.pack("<I", 0xF5) + bytes(8) + struct.pack("<I", _SCSI_POLL_SIZE)
        for attempt in range(_SCSI_BOOT_RETRIES + 1):
            cbw = bytearray(31)
            cbw[0:4] = b"USBC"
            cbw[4:8] = (attempt + 1).to_bytes(4, "little")
            cbw[8:12] = _SCSI_POLL_SIZE.to_bytes(4, "little")
            cbw[12] = 0x80          # data-IN
            cbw[14] = len(cdb)
            cbw[15:15 + len(cdb)] = cdb
            dev.write(ep_out, bytes(cbw), timeout=_TIMEOUT_MS)
            data = bytes(dev.read(ep_in, _SCSI_POLL_SIZE, timeout=_TIMEOUT_MS))
            dev.read(ep_in, 13, timeout=_TIMEOUT_MS)   # CSW, discard
            if len(data) >= 8 and data[4:8] == _SCSI_BOOT_SIGNATURE:
                time.sleep(_SCSI_BOOT_WAIT_S)          # device still booting
                continue
            return parse_scsi_poll(data)
        raise ProbeError("device still booting — try again in a few seconds")
    except usb.core.USBError as e:
        if e.errno == _EBUSY:
            raise ProbeError(
                "device is in use (service running?) — stop it or replug") from e
        raise ProbeError(f"SCSI probe failed: {e}") from e
    finally:
        if iface is not None:
            try:
                usb.util.release_interface(dev, iface)
            except Exception:
                pass
        usb.util.dispose_resources(dev)


# --- probe families --------------------------------------------------------------

def _probe_bulk(vid: int, pid: int) -> ProbeResult:
    return _run_usb_bulk(vid, pid, _BULK_HANDSHAKE, 1024, parse_bulk_response)


def _probe_hid_t2(vid: int, pid: int) -> ProbeResult:
    return _run_hid(vid, pid, _T2_INIT, 512, parse_hid_t2_response)


def _probe_hid_t3(vid: int, pid: int) -> ProbeResult:
    return _run_hid(vid, pid, _T3_INIT, 1024, parse_hid_t3_response)


def _probe_ly(vid: int, pid: int) -> ProbeResult:
    from thermalright_lcd_control.device_controller.display.transport import LyTransport
    return _run_usb_bulk(vid, pid, LyTransport._HANDSHAKE, 512,
                         lambda resp: parse_ly_response(resp, pid))


def _probe_scsi(vid: int, pid: int) -> ProbeResult:
    # Wrapper (not a direct reference) so the runner stays monkeypatchable,
    # like the other families that resolve their _run_* global at call time.
    return _run_scsi_poll(vid, pid)


# Family name → runner. The name is what registry entries reference in their
# ``probe:`` field, so adding a device to the registry never touches code.
PROBE_FAMILIES: dict[str, Callable[[int, int], ProbeResult]] = {
    "bulk": _probe_bulk,
    "hid_t2": _probe_hid_t2,
    "hid_t3": _probe_hid_t3,
    "ly": _probe_ly,
    "scsi": _probe_scsi,
}


def probe_device(vid: int, pid: int, family: str) -> ProbeResult:
    """Handshake the device with the given probe family. Raises ProbeError."""
    runner = PROBE_FAMILIES.get(family)
    if runner is None:
        raise ProbeError(f"unknown probe family '{family}' "
                         f"(known: {', '.join(sorted(PROBE_FAMILIES))})")
    result = runner(vid, pid)
    logger.info(
        f"probe {vid:04x}:{pid:04x} [{family}]: PM={result.pm} SUB={result.sub} "
        f"FBL={result.fbl} → {result.width}x{result.height} {result.encoding.value}")
    return result
