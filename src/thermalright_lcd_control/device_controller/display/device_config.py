# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Per-device active-config path resolution for the unified devices.yaml stack.

Both generic and legacy devices key the *active* config file by the device
``id`` (``config_<id>.yaml``) so several devices — even with the same
resolution — each keep their own active config. The id-keyed file is seeded
once from the resolution-keyed ``config_<w><h>.yaml`` for back-compat. Assets
(themes presets / foregrounds / backgrounds) stay keyed by resolution and are
untouched here.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

# Filenames must stay portable: allow word chars, dash and dot only.
_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def to_int(value, field: str = "value") -> int:
    """Parse an int given as int or hex/decimal string (e.g. ``0x0416``).

    Raises ``ValueError`` with a user-facing message naming ``field``."""
    if isinstance(value, bool):
        raise ValueError(f"{field}: invalid value")
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        raise ValueError(f"{field} is required")
    try:
        return int(s, 0)
    except ValueError:
        raise ValueError(f"{field}: '{s}' is not a valid integer") from None


def sanitize_id(device_id: str) -> str:
    """Make a device id safe to embed in a filename."""
    cleaned = _SAFE_ID.sub("_", str(device_id).strip())
    if not cleaned:
        raise ValueError("device id is empty after sanitisation")
    return cleaned


def active_config_path(config_dir: str | Path, device_id: str) -> Path:
    """Path of the per-device active config: ``<config_dir>/config_<id>.yaml``."""
    return Path(config_dir) / f"config_{sanitize_id(device_id)}.yaml"


def legacy_config_path(config_dir: str | Path, width: int, height: int) -> Path:
    """Resolution-keyed active config used before id-keying / by legacy mode."""
    return Path(config_dir) / f"config_{width}{height}.yaml"


def ensure_resolution_dir(path: str, asset_dir: str) -> str:
    """Insert a ``{resolution}`` folder into an asset path that lacks one.

    ``.../<asset_dir>/<file>`` → ``.../<asset_dir>/{resolution}/<file>``. Paths
    that already carry a sub-folder (a concrete ``<w><h>`` dir or the
    ``{resolution}`` placeholder) are returned unchanged. The loader substitutes
    ``{resolution}`` with ``<width><height>`` at read time.
    """
    if not isinstance(path, str):
        return path
    marker = f"/{asset_dir}/"
    i = path.find(marker)
    if i == -1:
        return path
    after = path[i + len(marker):]
    if "/" in after:  # already has "<resolution>/" or "{resolution}/"
        return path
    return f"{path[:i + len(marker)]}{{resolution}}/{after}"


def resolve_active_config(config_dir: str | Path, device_id: str,
                          width: int, height: int, *, seed: bool = True) -> Path:
    """Return the id-keyed active config path the generic device reads/watches.

    If the id-keyed file does not exist yet and ``seed`` is True, copy the
    resolution-keyed file into it once (non-destructive: the legacy file is
    kept). This lets an existing single-device setup keep working until the
    GUI writes the id-keyed file on the next Apply. The background path is
    repaired during the copy: legacy files stored it as ``backgrounds/<file>``,
    but the asset actually lives in ``backgrounds/<w><h>/<file>``.
    """
    target = active_config_path(config_dir, device_id)
    if not target.exists() and seed:
        legacy = legacy_config_path(config_dir, width, height)
        if legacy.exists():
            _seed_from_legacy(legacy, target)
    return target


def _seed_from_legacy(legacy: Path, target: Path) -> None:
    """Copy ``legacy`` to ``target``, repairing the background asset path."""
    data = yaml.safe_load(legacy.read_text())
    try:
        background = data["display"]["background"]
        background["path"] = ensure_resolution_dir(background["path"], "backgrounds")
    except (KeyError, TypeError):
        pass  # unexpected shape: copy as-is rather than fail seeding
    target.write_text(yaml.dump(data, sort_keys=False))
