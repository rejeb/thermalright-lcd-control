# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Tests for the probe registry (known devices → probe family)."""
from pathlib import Path

from thermalright_lcd_control.device_controller.display.device_probe import (
    PROBE_FAMILIES,
)
from thermalright_lcd_control.device_controller.display.probe_registry import (
    PROBE_REGISTRY_DIR,
    find_registry_entry,
    load_registry,
)


class TestBundledRegistry:
    def test_dir_exists_with_nine_entries(self):
        assert PROBE_REGISTRY_DIR.is_dir()
        entries = load_registry()
        assert len(entries) == 9

    def test_all_entries_valid(self):
        for e in load_registry():
            assert isinstance(e["vid"], int) and 0 < e["vid"] <= 0xFFFF
            assert isinstance(e["pid"], int) and 0 < e["pid"] <= 0xFFFF
            assert e["probe"] in PROBE_FAMILIES
            assert e["name"]

    def test_expected_families(self):
        by_key = {(e["vid"], e["pid"]): e["probe"] for e in load_registry()}
        assert by_key[(0x87AD, 0x70DB)] == "bulk"
        assert by_key[(0x87CD, 0x70DB)] == "scsi"     # SCSI wire, not bulk
        assert by_key[(0x0416, 0x5302)] == "hid_t2"
        assert by_key[(0x0418, 0x5303)] == "hid_t3"
        assert by_key[(0x0418, 0x5304)] == "hid_t3"
        assert by_key[(0x0416, 0x5408)] == "ly"
        assert by_key[(0x0416, 0x5409)] == "ly"
        assert by_key[(0x0402, 0x3922)] == "scsi"
        assert by_key[(0x0416, 0x5406)] == "scsi"


class TestExtraDirs:
    def test_user_entry_added(self, tmp_path: Path):
        (tmp_path / "mydev.yaml").write_text(
            "vid: 0x1234\npid: 0x5678\nname: My device\nprobe: bulk\n")
        entries = load_registry(extra_dirs=(tmp_path,))
        assert len(entries) == 10
        assert find_registry_entry(0x1234, 0x5678, extra_dirs=(tmp_path,))

    def test_user_entry_overrides_bundled(self, tmp_path: Path):
        (tmp_path / "override.yaml").write_text(
            "vid: 0x87AD\npid: 0x70DB\nname: Patched\nprobe: scsi\n")
        entry = find_registry_entry(0x87AD, 0x70DB, extra_dirs=(tmp_path,))
        assert entry["probe"] == "scsi"
        assert entry["name"] == "Patched"
        assert len(load_registry(extra_dirs=(tmp_path,))) == 9   # replaced, not added

    def test_missing_dir_is_ignored(self, tmp_path: Path):
        assert len(load_registry(extra_dirs=(tmp_path / "nope",))) == 9


class TestBadEntries:
    def test_malformed_yaml_skipped(self, tmp_path: Path):
        (tmp_path / "broken.yaml").write_text("vid: [unclosed\n")
        assert len(load_registry(extra_dirs=(tmp_path,))) == 9

    def test_unknown_family_skipped(self, tmp_path: Path):
        (tmp_path / "warp.yaml").write_text(
            "vid: 0x1111\npid: 0x2222\nname: Warp\nprobe: warp\n")
        assert len(load_registry(extra_dirs=(tmp_path,))) == 9

    def test_missing_fields_skipped(self, tmp_path: Path):
        (tmp_path / "nofields.yaml").write_text("name: incomplete\n")
        assert len(load_registry(extra_dirs=(tmp_path,))) == 9


class TestFind:
    def test_hit(self):
        entry = find_registry_entry(0x0416, 0x5302)
        assert entry is not None and entry["probe"] == "hid_t2"

    def test_miss(self):
        assert find_registry_entry(0xDEAD, 0xBEEF) is None
