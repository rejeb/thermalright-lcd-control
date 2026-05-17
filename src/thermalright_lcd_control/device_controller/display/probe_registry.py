# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Probe registry: which handshake family each known VID:PID speaks.

trcc-style device knowledge as data: one YAML file per device under
``probe_registry/``, holding ``vid``, ``pid``, ``name`` and ``probe`` (a
family name from :data:`device_probe.PROBE_FAMILIES`). Detection walks this
registry — the transport dialect cannot be inferred from USB descriptors, it
has to come from prior knowledge of the VID:PID.

``load_registry(extra_dirs=...)`` is the extension hook for the upcoming
"user adds a device to the registry" feature: later directories override
bundled entries with the same (vid, pid), so a user file can both add and
patch devices without code changes.
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from thermalright_lcd_control.device_controller.display.device_config import to_int
from thermalright_lcd_control.device_controller.display.device_probe import (
    PROBE_FAMILIES,
)

logger = logging.getLogger(__name__)

PROBE_REGISTRY_DIR = Path(__file__).parent / "probe_registry"


def _load_entry(path: Path) -> dict | None:
    """One registry file → validated entry dict, or None if unusable."""
    try:
        data = yaml.safe_load(path.read_text()) or {}
        vid, pid = to_int(data["vid"], "vid"), to_int(data["pid"], "pid")
        probe = str(data["probe"])
    except (yaml.YAMLError, KeyError, ValueError, TypeError, OSError) as e:
        logger.warning(f"probe registry: skipping {path.name}: {e}")
        return None
    if not (0 < vid <= 0xFFFF and 0 < pid <= 0xFFFF):
        logger.warning(f"probe registry: skipping {path.name}: bad vid/pid")
        return None
    if probe not in PROBE_FAMILIES:
        logger.warning(
            f"probe registry: skipping {path.name}: unknown probe family "
            f"'{probe}' (known: {', '.join(sorted(PROBE_FAMILIES))})")
        return None
    return {"vid": vid, "pid": pid, "probe": probe,
            "name": str(data.get("name") or f"{vid:04x}:{pid:04x}")}


def load_registry(extra_dirs: tuple[Path | str, ...] = ()) -> list[dict]:
    """All registry entries, deduped by (vid, pid); later dirs override.

    ``extra_dirs`` is reserved for user-added registry entries: entries found
    there replace bundled ones with the same (vid, pid).
    """
    entries: dict[tuple[int, int], dict] = {}
    for directory in (PROBE_REGISTRY_DIR, *map(Path, extra_dirs)):
        if not directory.is_dir():
            continue
        for f in sorted(directory.glob("*.yaml")):
            entry = _load_entry(f)
            if entry is not None:
                entries[(entry["vid"], entry["pid"])] = entry
    return list(entries.values())


def find_registry_entry(vid: int, pid: int,
                        extra_dirs: tuple[Path | str, ...] = ()) -> dict | None:
    """The registry entry for (vid, pid), or None if the device is unknown."""
    for entry in load_registry(extra_dirs):
        if (entry["vid"], entry["pid"]) == (vid, pid):
            return entry
    return None
