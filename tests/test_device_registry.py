import tempfile
import unittest

import yaml

from thermalright_lcd_control.device_controller.display import device_registry as reg

_LSUSB_SAMPLE = """\
Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
Bus 001 Device 003: ID 0416:5302 Winbond Electronics Corp. LCD
Bus 001 Device 003: ID 0416:5302 Winbond Electronics Corp. LCD
Bus 001 Device 005: ID 8087:0024 Intel Corp. Integrated Rate Matching Hub
"""


class TestParseLsusb(unittest.TestCase):
    def test_parses_bus_device_and_dedups_by_address(self):
        out = reg.parse_lsusb(_LSUSB_SAMPLE)
        keys = {(d["vid"], d["pid"]) for d in out}
        self.assertIn((0x0416, 0x5302), keys)
        self.assertIn((0x8087, 0x0024), keys)
        # the two identical bus/device lines collapse to one
        wb = [d for d in out if d["vid"] == 0x0416 and d["pid"] == 0x5302]
        self.assertEqual(len(wb), 1)
        self.assertEqual((wb[0]["bus"], wb[0]["device"]), (1, 3))

    def test_label_includes_address(self):
        out = reg.parse_lsusb("Bus 001 Device 003: ID 0416:5302 Winbond LCD\n")
        self.assertEqual(out[0]["label"], "0416:5302  Winbond LCD  (bus 1/dev 3)")

    def test_empty_input(self):
        self.assertEqual(reg.parse_lsusb(""), [])


class TestBuildEntry(unittest.TestCase):
    def _form(self, **over):
        f = {"id": "my_dev", "vid": "0x0416", "pid": "0x5302", "width": "320",
             "height": "240", "transport": "hid", "encoding": "rgb565_le_columns"}
        f.update(over)
        return f

    def test_minimal_entry(self):
        e = reg.build_device_entry(self._form())
        self.assertEqual(e["id"], "my_dev")
        self.assertEqual(e["vid"], "0x0416")
        self.assertEqual(e["pid"], "0x5302")
        self.assertEqual(e["width"], 320)
        self.assertEqual(e["chunk_size"], 4096)
        self.assertNotIn("header", e)

    def test_optional_and_header(self):
        e = reg.build_device_entry(self._form(
            encoding="jpeg", jpeg_quality="90", start_wait="2",
            ep_in="0x81", command="0xF5",
            header='{"prefix":"12345678","values":["cmd","width",2]}'))
        self.assertEqual(e["jpeg_quality"], 90)
        self.assertEqual(e["start_wait"], 2.0)
        self.assertEqual(e["ep_in"], "0x81")
        self.assertEqual(e["header"]["values"], ["cmd", "width", 2])

    def test_generic_defaults_true(self):
        e = reg.build_device_entry(self._form())
        self.assertIs(e["generic"], True)

    def test_native_keeps_full_generic_config(self):
        # Even when generic=False (hard-coded/native driver), the complete
        # generic config must be persisted so the entry is self-contained.
        e = reg.build_device_entry(self._form(generic=False))
        self.assertIs(e["generic"], False)
        self.assertEqual(e["width"], 320)
        self.assertEqual(e["transport"], "hid")
        self.assertEqual(e["encoding"], "rgb565_le_columns")

    def test_missing_id_raises(self):
        with self.assertRaises(ValueError):
            reg.build_device_entry(self._form(id="  "))

    def test_bad_transport_raises(self):
        with self.assertRaises(ValueError):
            reg.build_device_entry(self._form(transport="nope"))

    def test_bad_encoding_raises(self):
        with self.assertRaises(ValueError):
            reg.build_device_entry(self._form(encoding="nope"))

    def test_bad_header_json_raises(self):
        with self.assertRaises(ValueError):
            reg.build_device_entry(self._form(header="{not json"))

    def test_id_with_space_normalized_to_underscore(self):
        e = reg.build_device_entry(self._form(id="my dev  2"))
        self.assertEqual(e["id"], "my_dev_2")
        self.assertNotIn(" ", e["id"])


class TestSuggestId(unittest.TestCase):
    def test_format_is_pid_vid_bus_device(self):
        self.assertEqual(reg.suggest_id([], "0x0416", "0x5302", "1", "3"),
                         "5302_0416_1_3")

    def test_no_address_falls_back_to_pid_vid(self):
        self.assertEqual(reg.suggest_id([], "0x0416", "0x5302", "", ""),
                         "5302_0416")

    def test_two_identical_devices_distinct_by_address(self):
        a = reg.suggest_id([], "0x0416", "0x5302", "1", "3")
        b = reg.suggest_id([], "0x0416", "0x5302", "2", "5")
        self.assertNotEqual(a, b)
        self.assertEqual((a, b), ("5302_0416_1_3", "5302_0416_2_5"))

    def test_unique_suffix_on_collision(self):
        existing = [{"id": "5302_0416_1_3"}]
        self.assertEqual(reg.suggest_id(existing, "0x0416", "0x5302", "1", "3"),
                         "5302_0416_1_3_2")

    def test_no_spaces_in_generated_id(self):
        self.assertNotIn(" ", reg.suggest_id([], "0x0416", "0x5302", "1", "3"))

    def test_invalid_vid_returns_empty(self):
        self.assertEqual(reg.suggest_id([], "", "0x5302", "1", "3"), "")


class TestDeviceFiles(unittest.TestCase):
    """Per-device ``device_<id>.yaml`` persistence."""

    def _entry(self, **over):
        f = {"id": "dev_a", "vid": "0x0416", "pid": "0x5302", "width": "320",
             "height": "240", "transport": "hid", "encoding": "rgb565_le_columns"}
        f.update(over)
        return reg.build_device_entry(f)

    def test_write_creates_file_and_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            reg.write_device_entry(d, self._entry(id="new_dev", vid="0x87AD",
                                                  pid="0x70DB", width="640",
                                                  transport="usb_bulk",
                                                  encoding="jpeg"))
            path = reg.device_file_path(d, "new_dev")
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "device_new_dev.yaml")
            data = yaml.safe_load(path.read_text())
            self.assertEqual(data["id"], "new_dev")
            self.assertEqual(int(data["vid"], 0), 0x87AD)
            self.assertEqual(data["width"], 640)

    def test_duplicate_id_raises(self):
        with tempfile.TemporaryDirectory() as d:
            reg.write_device_entry(d, self._entry(id="dup"))
            with self.assertRaises(ValueError):
                reg.write_device_entry(d, self._entry(id="dup"))

    def test_get_device_returns_normalized_entry(self):
        with tempfile.TemporaryDirectory() as d:
            reg.write_device_entry(d, self._entry(id="dev_a"))
            cfg = reg.get_device(d, "dev_a")
            self.assertEqual(cfg["id"], "dev_a")
            self.assertEqual(cfg["vid"], "0x0416")   # normalized to hex string
            self.assertIsNone(reg.get_device(d, "nope"))

    def test_list_devices_returns_all_files(self):
        with tempfile.TemporaryDirectory() as d:
            reg.write_device_entry(d, self._entry(id="dev_a"))
            reg.write_device_entry(d, self._entry(id="dev_b", vid="0x87AD",
                                                  pid="0x70DB", width="480",
                                                  height="480",
                                                  transport="usb_bulk",
                                                  encoding="jpeg"))
            ids = sorted(x["id"] for x in reg.list_devices(d))
            self.assertEqual(ids, ["dev_a", "dev_b"])

    def test_update_replaces_entry_in_place(self):
        with tempfile.TemporaryDirectory() as d:
            reg.write_device_entry(d, self._entry(id="dev_a"))
            reg.update_device_entry(d, "dev_a",
                                    self._entry(id="dev_a", width="640",
                                                encoding="jpeg"))
            cfg = reg.get_device(d, "dev_a")
            self.assertEqual(cfg["width"], 640)
            self.assertEqual(cfg["encoding"], "jpeg")

    def test_update_rename_id_moves_file(self):
        with tempfile.TemporaryDirectory() as d:
            reg.write_device_entry(d, self._entry(id="old_id"))
            reg.update_device_entry(d, "old_id", self._entry(id="new_id"))
            self.assertFalse(reg.device_file_path(d, "old_id").exists())
            self.assertTrue(reg.device_file_path(d, "new_id").exists())
            self.assertEqual([x["id"] for x in reg.list_devices(d)], ["new_id"])

    def test_update_missing_device_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                reg.update_device_entry(d, "ghost", self._entry(id="ghost"))

    def test_remove_deletes_file(self):
        with tempfile.TemporaryDirectory() as d:
            reg.write_device_entry(d, self._entry(id="dev_a"))
            reg.remove_device_entry(d, "dev_a")
            self.assertFalse(reg.device_file_path(d, "dev_a").exists())
            with self.assertRaises(ValueError):
                reg.remove_device_entry(d, "dev_a")


if __name__ == "__main__":
    unittest.main()
