# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Tests for device_registry.detect_device / detect_devices (registry-driven).

Detection needs no bundled per-device profile: the probe registry names the
wire family, the handshake reports the screen, and the wire-protocol constants
the handshake does not carry (frame header, HID report id, chunk size, command
byte) come from the family-defaults table.
"""
from thermalright_lcd_control.device_controller.display.device_probe import (
    ProbeError,
    ProbeResult,
)
from thermalright_lcd_control.device_controller.display.device_registry import (
    detect_device,
    detect_devices,
    list_devices,
    register_detected_devices,
)
from thermalright_lcd_control.device_controller.display.image_encoder import ImageEncoding
from thermalright_lcd_control.device_controller.display.transport import TransportType


def _probe_bulk_jpeg(vid, pid):
    return ProbeResult(TransportType.USB_BULK, 480, 480,
                       ImageEncoding.JPEG, pm=1, sub=0, fbl=72)


def _probe_5302(vid, pid):
    return ProbeResult(TransportType.HID, 320, 240,
                       ImageEncoding.RGB565_LE_COLUMNS, pm=51, sub=0, fbl=51)


class TestDetectDevice:
    def test_hid_t2_gets_family_header(self):
        # The 5302 regression: with no bundled profile the frame header must
        # still come from the hid_t2 wire family, or the panel ignores frames.
        out = detect_device(0x0416, 0x5302, probe=_probe_5302)
        assert out["detected"] is True
        cfg = out["config"]
        assert (cfg["width"], cfg["height"]) == (320, 240)
        assert cfg["transport"] == "hid"
        assert cfg["encoding"] == "rgb565_le_columns"
        assert cfg["chunk_size"] == 4096            # family override, not 512
        assert cfg["report_id"] == "00"
        assert cfg["header"]["prefix"] == "DADBDCDD"
        assert cfg["header"]["values"][2] == "width"
        assert cfg["vid"] == "0x0416"               # form-normalized
        assert "hid_t2" in out["message"]

    def test_bulk_jpeg_resolves_cmd_2(self):
        out = detect_device(0x87AD, 0x70DB, probe=_probe_bulk_jpeg)
        cfg = out["config"]
        assert cfg["encoding"] == "jpeg"
        assert cfg["cmd"] == 2                       # JPEG → cmd 2
        assert cfg["header"]["prefix"] == "12345678"
        assert cfg["chunk_size"] == 16384

    def test_bulk_rgb565_resolves_cmd_3(self):
        def probe_raw(vid, pid):
            return ProbeResult(TransportType.USB_BULK, 320, 320,
                               ImageEncoding.RGB565_BE, pm=32, sub=0, fbl=100)
        out = detect_device(0x87AD, 0x70DB, probe=probe_raw)
        assert out["config"]["cmd"] == 3            # raw RGB565 → cmd 3

    def test_ly_has_no_header(self):
        def probe_ly(vid, pid):
            return ProbeResult(TransportType.USB_BULK_LY, 1920, 462,
                               ImageEncoding.JPEG, pm=65, sub=1, fbl=192)
        out = detect_device(0x0416, 0x5408, probe=probe_ly)
        assert out["detected"] is True
        cfg = out["config"]
        assert (cfg["width"], cfg["height"]) == (1920, 462)
        assert cfg["transport"] == "usb_bulk_ly"
        assert cfg["chunk_size"] == 512
        assert "header" not in cfg                  # LY carries no frame header
        assert "report_id" not in cfg

    def test_probe_failure_yields_no_config(self):
        def probe_fail(vid, pid):
            raise ProbeError("device is in use")
        out = detect_device(0x0416, 0x5302, probe=probe_fail)
        assert out["detected"] is False
        assert out["config"] is None
        assert "in use" in out["message"]

    def test_unknown_vidpid_gated_by_registry(self):
        # Not in the probe registry → answered before any probe runs.
        out = detect_device(0x1234, 0x5678, probe=_probe_5302)
        assert out["detected"] is False
        assert out["config"] is None
        assert "not in probe registry" in out["message"]


class _FakeUsbDev:
    def __init__(self, bus: int, address: int):
        self.bus = bus
        self.address = address


class TestDetectDevices:
    def test_scans_registry_and_probes_present(self):
        def fake_find(find_all=False, idVendor=None, idProduct=None):
            if (idVendor, idProduct) == (0x87AD, 0x70DB):
                return [_FakeUsbDev(3, 7)]
            return []

        out = detect_devices(probe=_probe_bulk_jpeg, find=fake_find)
        assert len(out) == 1
        d = out[0]
        assert d["detected"] is True
        assert d["config"]["width"] == 480
        assert d["name"] == "ChiZhu GrandVision family"
        assert (d["bus"], d["device"]) == (3, 7)

    def test_two_identical_devices_both_reported(self):
        def fake_find(find_all=False, idVendor=None, idProduct=None):
            if (idVendor, idProduct) == (0x87AD, 0x70DB):
                return [_FakeUsbDev(1, 4), _FakeUsbDev(1, 5)]
            return []

        out = detect_devices(probe=_probe_bulk_jpeg, find=fake_find)
        assert [(d["bus"], d["device"]) for d in out] == [(1, 4), (1, 5)]

    def test_nothing_connected(self):
        out = detect_devices(probe=_probe_bulk_jpeg, find=lambda **kw: [])
        assert out == []

    def test_probe_failure_still_listed(self):
        def fake_find(find_all=False, idVendor=None, idProduct=None):
            if (idVendor, idProduct) == (0x0416, 0x5302):
                return [_FakeUsbDev(2, 9)]
            return []

        def probe_fail(vid, pid):
            raise ProbeError("device is in use")

        out = detect_devices(probe=probe_fail, find=fake_find)
        assert len(out) == 1
        assert out[0]["detected"] is False
        assert out[0]["config"] is None
        assert out[0]["name"] == "Winbond USBDISPLAY (HID type 2)"


def _find_5302(find_all=False, idVendor=None, idProduct=None):
    if (idVendor, idProduct) == (0x0416, 0x5302):
        return [_FakeUsbDev(3, 4)]
    return []


class TestRegisterDetectedDevices:
    def test_new_device_registered_with_family_header(self, tmp_path):
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        added = register_detected_devices(config_dir, probe=_probe_5302,
                                          find=_find_5302)
        assert [e["id"] for e in added] == ["5302_0416_3_4"]
        entries = list_devices(config_dir)
        assert len(entries) == 1
        e = entries[0]
        assert (e["width"], e["height"]) == (320, 240)
        assert e["transport"] == "hid"
        assert e["encoding"] == "rgb565_le_columns"
        assert e["chunk_size"] == 4096
        assert e["report_id"] == "00"
        assert e["header"]["prefix"] == "DADBDCDD"
        assert e["generic"] is True

    def test_configured_vidpid_never_readded(self, tmp_path):
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        # User already configured this vid/pid (with their own settings).
        (config_dir / "device_mine.yaml").write_text(
            "id: mine\nvid: '0x0416'\npid: '0x5302'\nwidth: 999\nheight: 999\n"
            "transport: hid\nchunk_size: 4096\nencoding: rgb565_le_columns\n")
        added = register_detected_devices(config_dir, probe=_probe_5302,
                                          find=_find_5302)
        assert added == []
        assert list_devices(config_dir)[0]["width"] == 999   # untouched

    def test_idempotent_second_run_adds_nothing(self, tmp_path):
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        register_detected_devices(config_dir, probe=_probe_5302, find=_find_5302)
        again = register_detected_devices(config_dir, probe=_probe_5302,
                                          find=_find_5302)
        assert again == []
        assert len(list_devices(config_dir)) == 1

    def test_configured_vidpid_not_even_probed(self, tmp_path):
        # Startup runs this on every launch: already-configured devices must
        # not cost a USB handshake (the GUI and the service both call it).
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        (config_dir / "device_mine.yaml").write_text(
            "id: mine\nvid: '0x0416'\npid: '0x5302'\nwidth: 320\nheight: 240\n"
            "transport: hid\nchunk_size: 4096\nencoding: rgb565_le_columns\n")

        def probe_must_not_run(vid, pid):
            raise AssertionError("configured device was probed")

        added = register_detected_devices(config_dir, probe=probe_must_not_run,
                                          find=_find_5302)
        assert added == []

    def test_undetected_device_not_registered(self, tmp_path):
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()

        def probe_fail(vid, pid):
            raise ProbeError("device is in use")

        added = register_detected_devices(config_dir, probe=probe_fail,
                                          find=_find_5302)
        assert added == []
        assert list_devices(config_dir) == []
