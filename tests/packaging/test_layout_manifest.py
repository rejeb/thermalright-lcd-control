"""The layout manifest is the contract between install.sh and the packages."""
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parents[2] / "packaging" / "layout.manifest"


def parse_manifest():
    entries = []
    for lineno, raw in enumerate(MANIFEST.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw.split("\t")
        assert len(parts) == 3, (
            f"{MANIFEST}:{lineno}: expected 3 tab-separated fields, got {len(parts)}"
        )
        entries.append((parts[0], parts[1], parts[2]))
    return entries


def test_manifest_exists():
    assert MANIFEST.is_file(), f"missing {MANIFEST}"


def test_entries_are_well_formed():
    for kind, mode, path in parse_manifest():
        assert kind in {"d", "f", "t"}, f"bad type {kind!r} for {path}"
        assert len(mode) == 3 and mode.isdigit(), f"bad mode {mode!r} for {path}"
        assert path.startswith("/"), f"path must be absolute: {path}"


def test_no_usr_local():
    """Debian Policy forbids packages owning /usr/local; on ostree it is a symlink."""
    for _, _, path in parse_manifest():
        assert not path.startswith("/usr/local"), f"/usr/local is forbidden: {path}"


def test_launcher_and_udev_locations():
    paths = {path for _, _, path in parse_manifest()}
    assert "/usr/bin/thermalright-lcd-control-app" in paths
    assert "/usr/lib/udev/rules.d/99-thermalright.rules" in paths


def test_no_user_config_paths():
    """Per-user state is created by the launcher and owned by no package."""
    for _, _, path in parse_manifest():
        assert "/.config/" not in path, f"user config must not be in the manifest: {path}"


@pytest.mark.parametrize(
    "expected",
    [
        "/opt/thermalright-lcd-control/venv",
        "/opt/thermalright-lcd-control/python",
        "/opt/thermalright-lcd-control/resources",
    ],
)
def test_required_trees_present(expected):
    trees = {path for kind, _, path in parse_manifest() if kind == "t"}
    assert expected in trees
