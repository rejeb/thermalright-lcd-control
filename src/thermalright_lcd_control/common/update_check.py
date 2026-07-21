# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Startup update check against the GitHub Releases API.

Pure logic, no Qt: fetch the latest published release tag, compare it to the
running version and tell the caller whether a newer one exists. Every network
and parse failure is swallowed (returns ``None``) so the check can never block
or crash startup — it is a best-effort, silent notification.
"""
from __future__ import annotations

import json
import urllib.request
from importlib.metadata import PackageNotFoundError, version as _pkg_version

_PACKAGE = "thermalright-lcd-control"
_REPO = "rejeb/thermalright-lcd-control"

#: Human-facing releases page (opened from the notification).
RELEASES_URL = f"https://github.com/{_REPO}/releases"
#: Machine-readable "latest release" endpoint.
RELEASES_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"


def current_version() -> str:
    """Running app version from the installed package metadata (``0`` if absent)."""
    try:
        return _pkg_version(_PACKAGE)
    except PackageNotFoundError:
        return "0"


def fetch_latest_version(timeout: float = 3.0) -> str | None:
    """Latest published release version, or ``None`` on any error/timeout.

    Reads the GitHub Releases API ``tag_name`` and strips a leading ``v``
    (``v2.1.0`` → ``2.1.0``). Best-effort: network errors, non-JSON bodies and a
    missing ``tag_name`` all yield ``None``."""
    try:
        req = urllib.request.Request(
            RELEASES_API_URL,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": _PACKAGE})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name")
        if not tag:
            return None
        tag = str(tag).strip()
        return tag[1:] if tag[:1].lower() == "v" else tag
    except Exception:
        return None


def _parse(v: str) -> tuple[tuple[int, ...], str]:
    """Version string → ``(release_ints, prerelease)``.

    Splits on the first ``-`` into the numeric release (``2.1.0`` →
    ``(2, 1, 0)``; non-numeric components become 0) and a prerelease tag
    (``rc1`` for ``2.1.0-rc1``, else ``""``)."""
    release, _, pre = str(v).strip().partition("-")
    ints = tuple(int(c) if c.isdigit() else 0 for c in release.split("."))
    return ints, pre


def _key(v: str):
    """Comparable key. Trailing zeros are trimmed so ``2.0`` == ``2.0.0``. A
    version WITHOUT a prerelease outranks the same release WITH one (``2.1.0`` >
    ``2.1.0-rc1``); ``(0, ...)`` vs ``(1, tag)`` encodes that ordering."""
    ints, pre = _parse(v)
    ints = list(ints)
    while len(ints) > 1 and ints[-1] == 0:
        ints.pop()
    pre_key = (0, pre) if pre else (1,)      # release (1,) sorts above any (0, tag)
    return tuple(ints), pre_key


def is_newer(latest: str, current: str) -> bool:
    """True when ``latest`` is strictly newer than ``current`` (semver-ish:
    numeric release compared component-wise, prerelease ranked below release)."""
    return _key(latest) > _key(current)


def check_for_update(timeout: float = 3.0) -> str | None:
    """Latest version string if a newer release exists, else ``None``."""
    latest = fetch_latest_version(timeout=timeout)
    if latest and is_newer(latest, current_version()):
        return latest
    return None
