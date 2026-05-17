# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Helpers to discover devices and register them as ``device_<id>.yaml`` files.

Each device is one file, ``<config_dir>/device_<id>.yaml``, holding the entry
dict at top level (one device per file rather than a single ``devices.yaml``
list).

Pure logic (no Qt) so it is unit-testable:
- :func:`list_usb_devices` / :func:`parse_lsusb` — every USB device as ``lsusb``
  reports it (VID:PID + name).
- :func:`build_device_entry` — validate a UI form into a device entry.
- :func:`list_devices` / :func:`get_device` — read the per-device files.
- :func:`write_device_entry` / :func:`update_device_entry` /
  :func:`remove_device_entry` — create, edit and delete those files.
"""
from __future__ import annotations

import copy
import logging
import re
import subprocess
from pathlib import Path

import yaml

from thermalright_lcd_control.device_controller.display.device_config import sanitize_id, to_int
from thermalright_lcd_control.device_controller.display.image_encoder import ImageEncoding
from thermalright_lcd_control.device_controller.display.transport import TransportType

logger = logging.getLogger(__name__)

_LSUSB_RE = re.compile(
    r"Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)"
)


# --- parsing helpers ---------------------------------------------------------

# Shared with generic_device_loader; kept under its historical local name.
_to_int = to_int


def _hex4(value, field: str = "value") -> str:
    """4-digit hex, for 16-bit ids (VID/PID)."""
    return f"0x{_to_int(value, field):04X}"


def _hex(value, field: str = "value") -> str:
    """Compact hex (>=2 digits), for single bytes (ep_in / command)."""
    return f"0x{_to_int(value, field):02X}"


# --- discovery ---------------------------------------------------------------

def parse_lsusb(text: str) -> list[dict]:
    """Parse ``lsusb`` into ``[{vid, pid, bus, device, name, label}]``.

    Deduped by physical address (bus, device) so two identical VID:PID devices
    on different ports stay distinct.
    """
    seen: dict[tuple[int, int], dict] = {}
    for line in text.splitlines():
        m = _LSUSB_RE.search(line)
        if not m:
            continue
        bus, device = int(m.group(1)), int(m.group(2))
        vid, pid = int(m.group(3), 16), int(m.group(4), 16)
        if (bus, device) in seen:
            continue
        name = m.group(5).strip() or "Unknown device"
        seen[(bus, device)] = {
            "vid": vid, "pid": pid, "bus": bus, "device": device, "name": name,
            "label": f"{vid:04x}:{pid:04x}  {name}  (bus {bus}/dev {device})",
        }
    return sorted(seen.values(), key=lambda d: d["name"].lower())


def list_usb_devices() -> list[dict]:
    """All USB devices via ``lsusb`` (empty list if lsusb is unavailable)."""
    try:
        out = subprocess.check_output(["lsusb"], text=True)
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_lsusb(out)


def _normalize_known(cfg: dict) -> dict:
    """Make a known-device config JSON/form friendly (VID:PID as hex strings)."""
    out = dict(cfg)
    if "vid" in out:
        out["vid"] = _hex4(out["vid"])
    if "pid" in out:
        out["pid"] = _hex4(out["pid"])
    return out


# --- handshake-based detection (registry-driven, trcc-style) ------------------

# Default chunk size per transport when building an entry from a bare probe.
_PROBE_DEFAULT_CHUNK = {
    "hid": 512,
    "usb_bulk": 16384,
    "scsi": 65536,
    "usb_bulk_ly": 512,
}

# Wire-family protocol constants the handshake response does NOT carry.
#
# The probe only reports screen geometry + pixel encoding (from PM/SUB/FBL).
# The frame-header layout, HID report id, command byte and any chunk-size
# override are fixed properties of the wire family, which the probe registry
# names in its ``probe:`` field — so detection fills them in without any
# bundled per-device profile. ``width``/``height``/``payload_size``/``cmd``
# in a header are per-frame placeholders resolved by HeaderBuilder at send
# time; every other value is a protocol literal. (``cmd`` itself is resolved
# per encoding in :func:`_family_config`, not stored here.)
_FAMILY_DEFAULTS: dict[str, dict] = {
    "hid_t2": {
        "chunk_size": 4096,
        "report_id": "00",
        "header": {
            "prefix": "DADBDCDD",
            "format": "<6HIH",
            "values": [2, 1, "width", "height", 2, 0, "payload_size", 0],
        },
    },
    "hid_t3": {
        "report_id": "00",
        "header": {
            "format": "<BBHHH",
            "values": [0x69, 0x88, "width", "height", 0],
        },
    },
    "bulk": {
        "start_wait": 2.0,
        "header": {
            "prefix": "12345678",
            "format": "<3I40xII",
            "values": ["cmd", "width", "height", 2, "payload_size"],
        },
    },
    "scsi": {
        "command": 0xF5,
    },
    "ly": {},
}


def _family_config(family: str, result) -> dict:
    """Wire-family fields not carried in the handshake (header/report_id/…).

    The raw-bulk command byte depends on the probed encoding (3 = raw RGB565,
    2 = JPEG), so it is resolved here rather than stored statically.

    A family with no entry in :data:`_FAMILY_DEFAULTS` is logged loudly rather
    than silently degraded: header-less families (scsi/ly) are present as
    explicit entries, so a *missing* one means a new wire family was added to
    the probe registry without its protocol constants — the resulting config
    would have no frame header and the panel would display nothing.
    """
    if family not in _FAMILY_DEFAULTS:
        logger.warning(
            f"probe family '{family}' has no _FAMILY_DEFAULTS entry: the device "
            f"will get no frame header/report id and may display nothing")
        return {}
    cfg = copy.deepcopy(_FAMILY_DEFAULTS[family])
    if family == "bulk":
        cfg["cmd"] = 2 if result.encoding == ImageEncoding.JPEG else 3
    return cfg


def detect_device(vid: int, pid: int, probe=None,
                  registry_dirs: tuple = ()) -> dict:
    """Probe a connected device (registry-driven) → prefilled form config.

    The probe registry says which handshake family the VID:PID speaks; the
    device's answer says which screen it drives. No bundled per-device profile
    is needed: resolution and encoding come from the handshake, and the
    wire-protocol constants the handshake does not carry (frame header, HID
    report id, chunk size, command byte) are family defaults keyed by the
    probe family (see :data:`_FAMILY_DEFAULTS`). On probe failure ``config``
    is ``None`` so callers fall back to the manual add flow.

    ``probe(vid, pid) -> ProbeResult`` is injectable for tests; the default
    resolves the family from the probe registry and handshakes the hardware.
    """
    from thermalright_lcd_control.device_controller.display.device_probe import (
        ProbeError, probe_device,
    )
    from thermalright_lcd_control.device_controller.display.probe_registry import (
        find_registry_entry,
    )

    entry = find_registry_entry(vid, pid, extra_dirs=registry_dirs)
    if entry is None:
        return {"detected": False, "config": None, "pm": 0, "sub": 0, "fbl": 0,
                "message": f"{vid:04x}:{pid:04x} not in probe registry"}
    family = entry["probe"]

    try:
        result = (probe(vid, pid) if probe is not None
                  else probe_device(vid, pid, family))
    except ProbeError as e:
        return {"detected": False, "config": None,
                "pm": 0, "sub": 0, "fbl": 0, "message": str(e)}

    cfg = {
        "vid": vid, "pid": pid,
        "width": result.width, "height": result.height,
        "transport": result.transport.value,
        "chunk_size": _PROBE_DEFAULT_CHUNK[result.transport.value],
        "encoding": result.encoding.value,
    }
    # Family defaults last: they own chunk_size/header/etc. for the wire family.
    cfg.update(_family_config(family, result))
    message = (f"Detected {result.width}x{result.height} "
               f"(PM={result.pm}) — {family} wire family")
    return {"detected": True, "config": _normalize_known(cfg),
            "pm": result.pm, "sub": result.sub, "fbl": result.fbl,
            "message": message}


def detect_devices(registry_dirs: tuple = (),
                   probe=None, find=None) -> list[dict]:
    """trcc-style scan: probe every connected device the registry knows.

    Walks the probe registry, asks pyusb which entries are physically present
    (``find`` injectable for tests), and returns one ``detect_device`` result
    per attached unit, augmented with ``name`` (registry), ``bus`` and
    ``device`` (physical USB address, for ``suggest_id``).
    """
    from thermalright_lcd_control.device_controller.display.probe_registry import (
        load_registry,
    )

    if find is None:
        import usb.core
        find = usb.core.find

    out: list[dict] = []
    for entry in load_registry(extra_dirs=registry_dirs):
        vid, pid = entry["vid"], entry["pid"]
        for dev in (find(find_all=True, idVendor=vid, idProduct=pid) or []):
            result = detect_device(vid, pid, probe=probe,
                                   registry_dirs=registry_dirs)
            result["name"] = entry["name"]
            result["vid"] = f"0x{vid:04X}"
            result["pid"] = f"0x{pid:04X}"
            result["bus"] = getattr(dev, "bus", None)
            result["device"] = getattr(dev, "address", None)
            out.append(result)
    return out


def register_detected_devices(config_dir: str | Path,
                              registry_dirs: tuple = (),
                              probe=None, find=None) -> list[dict]:
    """Auto-register detected devices that aren't configured yet.

    Called by the service at startup so plugging a known device is
    zero-touch, trcc-style. Existing configuration always wins: a (vid, pid)
    that already has a ``device_<id>.yaml`` is never re-added or modified,
    and devices whose probe failed are left for the manual add flow.

    Returns the entries written (empty list when everything was known).
    """
    from thermalright_lcd_control.device_controller.display.probe_registry import (
        load_registry,
    )

    existing = list_devices(config_dir)
    taken: set[tuple[int, int]] = set()
    for e in existing:
        try:
            taken.add((_to_int(e.get("vid"), "vid"), _to_int(e.get("pid"), "pid")))
        except ValueError:
            continue

    if find is None:
        import usb.core
        find = usb.core.find

    added: list[dict] = []
    for reg in load_registry(extra_dirs=registry_dirs):
        vid, pid = reg["vid"], reg["pid"]
        # Configured pairs are skipped BEFORE any USB I/O: this runs on every
        # launch, and the steady state must not cost a handshake per device.
        if (vid, pid) in taken:
            continue
        for dev in (find(find_all=True, idVendor=vid, idProduct=pid) or []):
            if (vid, pid) in taken:
                continue   # second identical unit: one entry per (vid, pid)
            d = detect_device(vid, pid, probe=probe,
                              registry_dirs=registry_dirs)
            if not d.get("detected") or not d.get("config"):
                logger.info(f"auto-register {vid:04x}:{pid:04x} skipped: "
                            f"{d.get('message')}")
                continue
            form = dict(d["config"])
            form["id"] = suggest_id(existing + added, vid, pid,
                                    getattr(dev, "bus", None),
                                    getattr(dev, "address", None))
            # Mark the entry as auto-detected: these entries are managed by the
            # startup probe and must not be user-deletable in the UI.
            form["auto_detected"] = True
            try:
                entry = build_device_entry(form)
                write_device_entry(config_dir, entry)
            except (ValueError, OSError) as e:
                logger.warning(f"auto-register {vid:04x}:{pid:04x} failed: {e}")
                continue
            taken.add((vid, pid))
            added.append(entry)
    return added


# --- registration ------------------------------------------------------------

# Field order kept in the written YAML entry (readability).
_ENTRY_ORDER = ("id", "vid", "pid", "width", "height", "generic", "auto_detected",
                "transport", "chunk_size", "encoding", "report_id", "cmd",
                "command", "jpeg_quality", "ep_in", "start_wait", "header")


def build_device_entry(form: dict) -> dict:
    """Validate a UI form dict into a normalized ``devices.yaml`` entry.

    Raises ``ValueError`` with a user-facing message on invalid input.
    """
    # id never contains spaces: collapse any whitespace into underscores.
    device_id = re.sub(r"\s+", "_", str(form.get("id", "")).strip())
    if not device_id:
        raise ValueError("Device id is required")

    transport = str(form.get("transport", "")).strip()
    try:
        TransportType(transport)
    except ValueError:
        raise ValueError(f"Unknown transport '{transport}'") from None

    encoding = str(form.get("encoding", "")).strip()
    try:
        ImageEncoding(encoding)
    except ValueError:
        raise ValueError(f"Unknown encoding '{encoding}'") from None

    width = _to_int(form.get("width"), "width")
    height = _to_int(form.get("height"), "height")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    # Driver mode: generic (data-driven) by default, native/hard-coded when the
    # UI toggle is off. Either way the full generic config below is persisted so
    # the entry stays self-contained.
    generic = form.get("generic", True)
    if isinstance(generic, str):
        generic = generic.strip().lower() not in ("false", "0", "no", "")

    entry: dict = {
        "id": device_id,
        "vid": _hex4(form.get("vid"), "vid"),
        "pid": _hex4(form.get("pid"), "pid"),
        "width": width,
        "height": height,
        "generic": bool(generic),
        "transport": transport,
        "chunk_size": _to_int(form.get("chunk_size") or 4096, "chunk_size"),
        "encoding": encoding,
    }

    # Optional fields — only written when meaningfully provided.
    if form.get("auto_detected"):
        entry["auto_detected"] = True    # startup-probe entry: not user-deletable
    report_id = str(form.get("report_id", "")).strip()
    if report_id:
        entry["report_id"] = report_id
    if str(form.get("cmd", "")).strip():
        entry["cmd"] = _to_int(form["cmd"], "cmd")
    if str(form.get("command", "")).strip():
        entry["command"] = _hex(form["command"], "command")
    if str(form.get("jpeg_quality", "")).strip():
        entry["jpeg_quality"] = _to_int(form["jpeg_quality"], "jpeg_quality")
    if str(form.get("ep_in", "")).strip():
        entry["ep_in"] = _hex(form["ep_in"], "ep_in")
    if str(form.get("start_wait", "")).strip():
        entry["start_wait"] = float(form["start_wait"])

    header = form.get("header")
    if isinstance(header, str):
        header = header.strip()
        if header:
            import json
            try:
                header = json.loads(header)
            except json.JSONDecodeError as e:
                raise ValueError(f"header is not valid JSON: {e}") from e
        else:
            header = None
    if header:
        if not isinstance(header, dict):
            raise ValueError("header must be a JSON object")
        entry["header"] = header

    # Reorder keys for a tidy file.
    return {k: entry[k] for k in _ENTRY_ORDER if k in entry}


def suggest_id(existing: list[dict], vid, pid, bus=None, device=None) -> str:
    """Propose a unique device id as ``<pid>_<vid>_<bus>_<device>``.

    The physical USB address (bus + device number, as ``lsusb`` reports them)
    makes the id unique even between two identical VID:PID devices. When the
    address is unknown it falls back to ``<pid>_<vid>`` with a numeric suffix.
    All parts are digits / lowercase hex, so the id never contains spaces.
    """
    try:
        base = f"{_to_int(pid, 'pid'):04x}_{_to_int(vid, 'vid'):04x}"
    except ValueError:
        return ""
    try:
        base = f"{base}_{_to_int(bus, 'bus')}_{_to_int(device, 'device')}"
    except ValueError:
        pass  # address unknown → pid_vid only

    taken = {d.get("id") for d in existing}
    if base not in taken:
        return base
    i = 2
    while f"{base}_{i}" in taken:
        i += 1
    return f"{base}_{i}"


def device_file_path(config_dir: str | Path, device_id: str) -> Path:
    """Path of a device file: ``<config_dir>/device_<id>.yaml``."""
    return Path(config_dir) / f"device_{sanitize_id(device_id)}.yaml"


def list_devices(config_dir: str | Path) -> list[dict]:
    """Every ``device_<id>.yaml`` entry under ``config_dir`` (one file each).

    Ids are coerced to ``str`` so an unquoted id that YAML parsed as an int
    (e.g. ``5302_0416_3_4`` → ``530204163_4``) still names its file correctly.
    """
    out: list[dict] = []
    for f in sorted(Path(config_dir).glob("device_*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(data, dict) and data.get("id") is not None:
            data["id"] = str(data["id"])
            out.append(data)
    return out


def present_device_ids(config_dir: str | Path, find=None) -> set[str]:
    """Ids of configured devices whose ``(vid, pid)`` is currently plugged in.

    ``find`` is injectable for tests (defaults to ``usb.core.find``), matching
    the pattern used by :func:`detect_devices`.
    """
    if find is None:
        import usb.core
        find = usb.core.find
    present: set[str] = set()
    for entry in list_devices(config_dir):
        try:
            vid, pid = to_int(entry["vid"], "vid"), to_int(entry["pid"], "pid")
        except (KeyError, ValueError):
            continue
        if find(idVendor=vid, idProduct=pid) is not None:
            present.add(str(entry["id"]))
    return present


def get_device(config_dir: str | Path, device_id: str) -> dict | None:
    """Return the (form-normalized) entry for ``device_id``, or ``None``."""
    path = device_file_path(config_dir, device_id)
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text())
    except (yaml.YAMLError, OSError):
        return None
    return _normalize_known(data) if isinstance(data, dict) else None


def _dump_device(entry: dict) -> str:
    return yaml.dump(entry, sort_keys=False, default_flow_style=False,
                     allow_unicode=True, indent=2)


def write_device_entry(config_dir: str | Path, entry: dict) -> None:
    """Create ``device_<id>.yaml`` for ``entry``.

    Raises ``ValueError`` if a file for that id already exists.
    """
    target = device_file_path(config_dir, entry["id"])
    if target.exists():
        raise ValueError(f"A device with id '{entry['id']}' already exists")
    target.write_text(_dump_device(entry))


def update_device_entry(config_dir: str | Path, original_id: str,
                        entry: dict) -> None:
    """Rewrite the device file for ``original_id`` with ``entry``.

    If the id changed, the file is renamed accordingly. Raises ``ValueError``
    if the device is not found, or if the new id collides with another file.
    """
    src = device_file_path(config_dir, original_id)
    if not src.exists():
        raise ValueError(f"Device '{original_id}' not found")
    dst = device_file_path(config_dir, entry["id"])
    if dst != src and dst.exists():
        raise ValueError(f"A device with id '{entry['id']}' already exists")
    dst.write_text(_dump_device(entry))
    if dst != src:
        src.unlink()


def remove_device_entry(config_dir: str | Path, device_id: str) -> None:
    """Delete the device file for ``device_id``.

    Raises ``ValueError`` if it does not exist.
    """
    target = device_file_path(config_dir, device_id)
    if not target.exists():
        raise ValueError(f"Device '{device_id}' not found")
    target.unlink()
