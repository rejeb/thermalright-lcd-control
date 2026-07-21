# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Best-effort download of bundled background videos, with no GUI dependency
so both the GUI (``gui/backend/mixins/backgrounds.py``) and the headless
device-render service (``ConfigLoader``) can self-heal a missing bundled
``.mp4`` the same way."""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

from thermalright_lcd_control.common.logging_config import LoggerConfig

DEFAULT_MEDIA_ENDPOINT = "https://api.thermalright.com/"

_logger = LoggerConfig.setup_service_logger()


def download_bundled_background(name: str, dest: Path,
                                 media_endpoint: str = DEFAULT_MEDIA_ENDPOINT) -> None:
    """Download ``<name>.mp4`` from ``media_endpoint`` into ``dest``.

    URL: ``{media_endpoint}/bj<res>/<name>.mp4`` where ``<res>`` is
    ``dest.parent.name`` (the ``<w><h>`` or ``<h><w>`` resolution folder).
    Writes to a temp file first so a truncated ``.mp4`` is not left behind if
    the download fails midway."""
    endpoint = str(media_endpoint).rstrip("/")
    url = f"{endpoint}/bj{dest.parent.name}/{name}.mp4"
    _logger.info(f"Downloading bundled background: {url}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".mp4.part")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            if getattr(resp, "status", 200) >= 400:
                raise RuntimeError(f"HTTP {resp.status}")
            with open(tmp, "wb") as f:
                shutil.copyfileobj(resp, f)
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def ensure_background_downloaded(path: str, media_endpoint: str = DEFAULT_MEDIA_ENDPOINT) -> None:
    """If ``path`` is a bundled ``.mp4`` background missing on disk, download
    it. No-op for user-imported (``user_``/``collection_``) or non-``.mp4``
    paths, or files that already exist. Download failures are logged and
    swallowed — the caller's ``FrameManager`` already handles a missing
    background file."""
    p = Path(path)
    if (p.suffix.lower() != ".mp4"
            or p.name.startswith(("user_", "collection_","theme_"))
            or p.exists()):
        return
    try:
        download_bundled_background(p.stem, p, media_endpoint)
    except Exception as e:
        _logger.warning(f"ensure_background_downloaded failed for {path}: {e}")
