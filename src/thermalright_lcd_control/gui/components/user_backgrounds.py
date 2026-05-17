# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""User background library: originals + per-resolution materialized copies.

An uploaded background is stored UNMODIFIED as the original in ``originals_dir`` and a
resized copy is generated per device resolution in ``backgrounds_root/<WxH>/`` under the
SAME name (same stem), so the whole group is easy to find and delete. ``migrate_legacy``
adopts pre-existing ``user_*``/``collection_*`` files (stored unmodified) into this model.
"""
from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterable
from pathlib import Path

from thermalright_lcd_control.common.media_formats import IMAGE_EXTENSIONS
from thermalright_lcd_control.gui.components import media_resize

_IMAGE_EXT = frozenset(IMAGE_EXTENSIONS)


def _res_dir(backgrounds_root: Path, w: int, h: int) -> Path:
    return Path(backgrounds_root) / f"{w}{h}"


def import_originals(src_paths: list[Path], originals_dir: Path) -> Path:
    """Validate and copy upload(s) UNMODIFIED into ``originals_dir``. A single file →
    ``user_<name>`` ; several → a ``collection_<uuid8>/`` folder. Videos > 5 s raise
    ``media_resize.MediaTooLongError`` before anything is written."""
    originals_dir = Path(originals_dir)
    originals_dir.mkdir(parents=True, exist_ok=True)
    # refus des vidéos trop longues AVANT toute écriture
    for src in src_paths:
        if src.suffix.lower() in media_resize._VIDEO_EXT:
            if media_resize.probe_duration(src) > media_resize.MAX_VIDEO_SECONDS:
                raise media_resize.MediaTooLongError(
                    f"Video longer than {media_resize.MAX_VIDEO_SECONDS:.0f}s: {src.name}")
    if len(src_paths) == 1:
        src = src_paths[0]
        dest = originals_dir / f"user_{src.name}"
        shutil.copy2(src, dest)
        return dest
    coll = originals_dir / f"collection_{uuid.uuid4().hex[:8]}"
    coll.mkdir(parents=True, exist_ok=True)
    for src in src_paths:
        shutil.copy2(src, coll / src.name)
    return coll


def _materialize_entry(original: Path, backgrounds_root: Path, w: int, h: int) -> None:
    res = _res_dir(backgrounds_root, w, h)
    if original.is_dir():                       # collection
        dst_dir = res / original.name
        for img in sorted(original.iterdir()):
            if img.suffix.lower() in _IMAGE_EXT:
                target = dst_dir / img.name
                if not target.exists():
                    media_resize.materialize(img, dst_dir / img.stem, w, h)
        return
    # fichier simple : on garde le même stem ; l'extension finale dépend du type
    existing = list(res.glob(original.stem + ".*"))
    if existing:
        return                                  # déjà matérialisé (idempotent)
    media_resize.materialize(original, res / original.stem, w, h)


def materialize_for(originals_dir: Path, backgrounds_root: Path, w: int, h: int) -> None:
    originals_dir = Path(originals_dir)
    if not originals_dir.exists():
        return
    for original in sorted(originals_dir.iterdir()):
        if original.is_dir() or media_resize.is_supported(original):
            _materialize_entry(original, backgrounds_root, w, h)


def materialize_all(originals_dir: Path, backgrounds_root: Path,
                    resolutions: Iterable[tuple[int, int]]) -> None:
    """Materialize each resolution AND its rotated (HxW) variant."""
    expanded: list[tuple[int, int]] = []
    for (w, h) in resolutions:
        for res in ((w, h), (h, w)):
            if res not in expanded:
                expanded.append(res)
    for (w, h) in expanded:
        materialize_for(originals_dir, backgrounds_root, w, h)


def delete_user_background(name: str, originals_dir: Path, backgrounds_root: Path) -> None:
    """Remove the original AND every per-resolution copy sharing ``name``'s stem."""
    stem = Path(name).stem
    originals_dir = Path(originals_dir)
    backgrounds_root = Path(backgrounds_root)
    # original (fichier <stem>.* ou dossier collection <stem>)
    for p in list(originals_dir.glob(stem + ".*")) + [originals_dir / stem]:
        _remove(p)
    # copies par résolution
    for res in backgrounds_root.glob("*"):
        if not res.is_dir():
            continue
        for p in list(res.glob(stem + ".*")) + [res / stem]:
            _remove(p)


def migrate_legacy(originals_dir: Path, backgrounds_root: Path,
                   resolutions: Iterable[tuple[int, int]]) -> None:
    """Adopt pre-existing ``user_*``/``collection_*`` copies (stored unmodified) as
    originals, then regenerate resized copies for all ``resolutions``. Idempotent: skips
    entries whose original already exists."""
    originals_dir = Path(originals_dir)
    originals_dir.mkdir(parents=True, exist_ok=True)
    backgrounds_root = Path(backgrounds_root)
    resolutions = list(resolutions)
    for res in sorted(backgrounds_root.glob("*")):
        if not res.is_dir():
            continue
        for entry in sorted(res.iterdir()):
            name = entry.name
            if not (name.startswith("user_") or name.startswith("collection_")):
                continue
            if list(originals_dir.glob(Path(name).stem + ".*")) or (originals_dir / name).exists():
                continue                        # original déjà présent → rien à faire
            if entry.is_dir():
                shutil.copytree(entry, originals_dir / name)
            else:
                shutil.copy2(entry, originals_dir / name)
            # remplacer les copies historiques (stockées non redimensionnées) par des
            # versions correctement redimensionnées pour chaque résolution.
            _clear_copies(Path(name).stem, backgrounds_root)
            materialize_all(originals_dir, backgrounds_root, resolutions)


def _clear_copies(stem: str, backgrounds_root: Path) -> None:
    """Supprime toutes les copies par résolution partageant ``stem`` (pas l'original)."""
    for res in Path(backgrounds_root).glob("*"):
        if not res.is_dir():
            continue
        for p in list(res.glob(stem + ".*")) + [res / stem]:
            _remove(p)


def _remove(p: Path) -> None:
    try:
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    except OSError:
        pass
