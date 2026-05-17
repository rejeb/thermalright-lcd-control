# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Tests for handshake-based device probing (device_probe.py)."""
import pytest

from thermalright_lcd_control.device_controller.display.device_probe import (
    ProbeError,
    ProbeResult,
    pm_to_fbl,
    screen_for,
)
from thermalright_lcd_control.device_controller.display.image_encoder import ImageEncoding
from thermalright_lcd_control.device_controller.display.transport import TransportType


class TestPmToFbl:
    def test_identity_when_unmapped(self):
        # SCSI convention: PM == FBL for values without an override.
        assert pm_to_fbl(100) == 100
        assert pm_to_fbl(72) == 72

    def test_overrides(self):
        assert pm_to_fbl(5) == 50      # 320x240
        assert pm_to_fbl(7) == 64      # 640x480
        assert pm_to_fbl(32) == 100    # 320x320
        assert pm_to_fbl(63) == 114    # 1600x720
        assert pm_to_fbl(65) == 192    # 1920x462

    def test_compound_pm_sub(self):
        assert pm_to_fbl(1, 48) == 114
        assert pm_to_fbl(1, 49) == 192
        assert pm_to_fbl(1, 0) == 1    # sub not in table → plain override path


class TestScreenFor:
    def test_known_fbls(self):
        assert screen_for(50) == (320, 240, False, False)
        assert screen_for(100) == (320, 320, False, True)   # big-endian RGB565
        assert screen_for(72) == (480, 480, False, False)
        assert screen_for(114) == (1600, 720, True, False)  # JPEG

    def test_fbl_192_disambiguated_by_pm(self):
        assert screen_for(192, 65) == (1920, 462, True, False)   # default
        assert screen_for(192, 68) == (1280, 480, True, False)
        assert screen_for(192, 69) == (1920, 440, True, False)

    def test_fbl_224_disambiguated_by_pm(self):
        assert screen_for(224, 9) == (854, 480, True, False)     # default
        assert screen_for(224, 12) == (800, 480, True, False)
        assert screen_for(224, 15) == (640, 172, True, False)

    def test_unknown_fbl_is_none(self):
        assert screen_for(0) is None
        assert screen_for(255) is None


def test_probe_result_dataclass():
    r = ProbeResult(TransportType.HID, 320, 240,
                    ImageEncoding.RGB565_LE_COLUMNS, pm=58, sub=0, fbl=58)
    assert (r.width, r.height) == (320, 240)
    assert r.transport is TransportType.HID


def test_probe_error_is_runtime_error():
    assert issubclass(ProbeError, RuntimeError)


# --- response parsers ---------------------------------------------------------

from thermalright_lcd_control.device_controller.display.device_probe import (  # noqa: E402
    parse_bulk_response,
    parse_hid_t2_response,
    parse_hid_t3_response,
    parse_ly_response,
    parse_scsi_poll,
)


def _bulk_resp(pm: int, sub: int = 0) -> bytes:
    resp = bytearray(1024)
    resp[24] = pm
    resp[36] = sub
    return bytes(resp)


class TestParseBulk:
    def test_grandvision_480(self):
        r = parse_bulk_response(_bulk_resp(pm=1))
        assert (r.width, r.height) == (480, 480)
        assert r.encoding is ImageEncoding.JPEG      # every PM except 32
        assert r.transport is TransportType.USB_BULK

    def test_pm32_is_rgb565_320(self):
        r = parse_bulk_response(_bulk_resp(pm=32))
        assert (r.width, r.height) == (320, 320)
        assert r.encoding is ImageEncoding.RGB565_BE

    def test_pm7_is_640x480(self):
        r = parse_bulk_response(_bulk_resp(pm=7))
        assert (r.width, r.height) == (640, 480)

    def test_pm1_sub48_is_1600x720(self):
        r = parse_bulk_response(_bulk_resp(pm=1, sub=48))
        assert (r.width, r.height) == (1600, 720)

    def test_unknown_pm_clamps_to_480(self):
        # PM 200 is not a known bulk model; must NOT leak into pm_to_fbl.
        r = parse_bulk_response(_bulk_resp(pm=200))
        assert (r.width, r.height) == (480, 480)
        assert r.fbl == 72

    def test_invalid_raises(self):
        with pytest.raises(ProbeError):
            parse_bulk_response(b"\x00" * 41)     # resp[24] == 0
        with pytest.raises(ProbeError):
            parse_bulk_response(b"\x00" * 10)     # too short


def _t2_resp(pm: int, sub: int = 0) -> bytes:
    resp = bytearray(512)
    resp[0:4] = bytes([0xDA, 0xDB, 0xDC, 0xDD])
    resp[4] = sub
    resp[5] = pm
    resp[12] = 0x01
    return bytes(resp)


class TestParseHidT2:
    def test_pm58_is_320x240(self):
        r = parse_hid_t2_response(_t2_resp(pm=58))
        assert (r.width, r.height) == (320, 240)
        assert r.encoding is ImageEncoding.RGB565_LE_COLUMNS
        assert r.transport is TransportType.HID

    def test_pm54_is_360x360_jpeg(self):
        r = parse_hid_t2_response(_t2_resp(pm=54))
        assert (r.width, r.height) == (360, 360)
        assert r.encoding is ImageEncoding.JPEG

    def test_bad_magic_raises(self):
        bad = bytearray(_t2_resp(pm=58))
        bad[0] = 0x00
        with pytest.raises(ProbeError):
            parse_hid_t2_response(bytes(bad))

    def test_bad_status_byte_raises(self):
        bad = bytearray(_t2_resp(pm=58))
        bad[12] = 0x00
        with pytest.raises(ProbeError):
            parse_hid_t2_response(bytes(bad))

    def test_unknown_pm_raises(self):
        with pytest.raises(ProbeError):
            parse_hid_t2_response(_t2_resp(pm=255))


class TestParseHidT3:
    def test_0x65_is_fbl_100(self):
        resp = bytes([0x65]) + bytes(1023)
        r = parse_hid_t3_response(resp)
        assert r.fbl == 100
        assert (r.width, r.height) == (320, 320)
        assert r.encoding is ImageEncoding.RGB565_LE_COLUMNS
        assert r.transport is TransportType.HID

    def test_0x66_is_fbl_101(self):
        r = parse_hid_t3_response(bytes([0x66]) + bytes(1023))
        assert r.fbl == 101

    def test_bad_first_byte_raises(self):
        with pytest.raises(ProbeError):
            parse_hid_t3_response(bytes([0x01]) + bytes(1023))


def _ly_resp(b20: int = 1, b22: int = 1, b36: int = 0, b8: int = 1) -> bytes:
    resp = bytearray(512)
    resp[0], resp[1], resp[8] = 3, 0xFF, b8
    resp[20], resp[22], resp[36] = b20, b22, b36
    return bytes(resp)


class TestParseLy:
    def test_5408_pm_from_byte20(self):
        r = parse_ly_response(_ly_resp(b20=1), pid=0x5408)
        assert r.pm == 65                       # 64 + 1
        assert (r.width, r.height) == (1920, 462)
        assert r.encoding is ImageEncoding.JPEG
        assert r.transport is TransportType.USB_BULK_LY

    def test_5408_low_raw_clamps_to_1(self):
        r = parse_ly_response(_ly_resp(b20=3), pid=0x5408)
        assert r.pm == 65                       # raw<=3 → 1 → 64+1

    def test_5409_pm_from_byte36(self):
        r = parse_ly_response(_ly_resp(b36=15), pid=0x5409)
        assert r.pm == 65                       # 50 + 15

    def test_byte8_2_accepted(self):
        # Real Trofeo Vision 9.16 hardware (0416:5408) answers resp[8]=2 even
        # though TRCC validates ==1; observed 2026-07-11 on bus 3 dev 5.
        r = parse_ly_response(_ly_resp(b20=0, b8=2), pid=0x5408)
        assert (r.width, r.height) == (1920, 462)
        assert r.pm == 65

    def test_invalid_raises(self):
        with pytest.raises(ProbeError):
            parse_ly_response(bytes(512), pid=0x5408)
        bad = bytearray(_ly_resp())
        bad[8] = 0
        with pytest.raises(ProbeError):
            parse_ly_response(bytes(bad), pid=0x5408)


class TestParseScsiPoll:
    def test_fbl_100(self):
        r = parse_scsi_poll(bytes([100]) + bytes(63))
        assert (r.width, r.height) == (320, 320)
        assert r.encoding is ImageEncoding.RGB565_BE
        assert r.transport is TransportType.SCSI

    def test_empty_raises(self):
        with pytest.raises(ProbeError):
            parse_scsi_poll(b"")

    def test_unknown_fbl_raises(self):
        with pytest.raises(ProbeError):
            parse_scsi_poll(bytes([250]) + bytes(63))


# --- probe families / dispatch --------------------------------------------------

from thermalright_lcd_control.device_controller.display import device_probe  # noqa: E402
from thermalright_lcd_control.device_controller.display.device_probe import (  # noqa: E402
    PROBE_FAMILIES,
    probe_device,
)


class TestProbeDispatch:
    def test_families_are_complete(self):
        assert set(PROBE_FAMILIES) == {"bulk", "hid_t2", "hid_t3", "ly", "scsi"}

    def test_unknown_family_raises(self):
        with pytest.raises(ProbeError, match="[Uu]nknown probe family"):
            probe_device(0x1234, 0x5678, "warp")

    def test_bulk_dispatches_to_usb_runner(self, monkeypatch):
        calls = {}

        def fake_run(vid, pid, payload, read_size, parse):
            calls["args"] = (vid, pid, payload[:4], len(payload), read_size)
            return parse(_bulk_resp(pm=1))

        monkeypatch.setattr(device_probe, "_run_usb_bulk", fake_run)
        r = probe_device(0x87AD, 0x70DB, "bulk")
        assert calls["args"] == (0x87AD, 0x70DB,
                                 bytes([0x12, 0x34, 0x56, 0x78]), 64, 1024)
        assert (r.width, r.height) == (480, 480)

    def test_hid_t2_dispatches_to_hid_runner(self, monkeypatch):
        def fake_run(vid, pid, init, read_size, parse):
            assert init[:4] == bytes([0xDA, 0xDB, 0xDC, 0xDD])
            assert len(init) == 512 and read_size == 512
            return parse(_t2_resp(pm=58))

        monkeypatch.setattr(device_probe, "_run_hid", fake_run)
        r = probe_device(0x0416, 0x5302, "hid_t2")
        assert (r.width, r.height) == (320, 240)

    def test_hid_t3_dispatches_to_hid_runner(self, monkeypatch):
        def fake_run(vid, pid, init, read_size, parse):
            assert init[:8] == bytes([0xF5, 0x00, 0x01, 0x00, 0xBC, 0xFF, 0xB6, 0xC8])
            assert len(init) == 1040 and read_size == 1024
            return parse(bytes([0x65]) + bytes(1023))

        monkeypatch.setattr(device_probe, "_run_hid", fake_run)
        r = probe_device(0x0418, 0x5304, "hid_t3")
        assert (r.width, r.height) == (320, 320)

    def test_ly_dispatches_with_pid_aware_parser(self, monkeypatch):
        def fake_run(vid, pid, payload, read_size, parse):
            assert len(payload) == 2048 and read_size == 512
            return parse(_ly_resp(b20=1))

        monkeypatch.setattr(device_probe, "_run_usb_bulk", fake_run)
        r = probe_device(0x0416, 0x5408, "ly")
        assert r.transport is TransportType.USB_BULK_LY
        assert r.pm == 65

    def test_scsi_dispatches_to_scsi_runner(self, monkeypatch):
        monkeypatch.setattr(
            device_probe, "_run_scsi_poll",
            lambda vid, pid: parse_scsi_poll(bytes([100]) + bytes(63)))
        r = probe_device(0x0402, 0x3922, "scsi")
        assert (r.width, r.height) == (320, 320)
