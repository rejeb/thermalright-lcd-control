# SPDX-License-Identifier: Apache-2.0
"""Startup update check: version comparison and best-effort GitHub fetch."""
import json
import unittest
from unittest import mock

from thermalright_lcd_control.common import update_check


class TestIsNewer(unittest.TestCase):
    def test_strictly_newer(self):
        self.assertTrue(update_check.is_newer("2.1.0", "2.0.0"))
        self.assertTrue(update_check.is_newer("2.0.1", "2.0.0"))
        self.assertTrue(update_check.is_newer("3.0.0", "2.9.9"))

    def test_older(self):
        self.assertFalse(update_check.is_newer("2.0.0", "2.1.0"))
        self.assertFalse(update_check.is_newer("1.9.9", "2.0.0"))

    def test_equal(self):
        self.assertFalse(update_check.is_newer("2.0.0", "2.0.0"))

    def test_differing_lengths_equal(self):
        # 2.0 and 2.0.0 are the same version
        self.assertFalse(update_check.is_newer("2.0", "2.0.0"))
        self.assertFalse(update_check.is_newer("2.0.0", "2.0"))
        self.assertTrue(update_check.is_newer("2.0.1", "2.0"))

    def test_prerelease_is_older_than_release(self):
        self.assertTrue(update_check.is_newer("2.1.0", "2.1.0-rc1"))
        self.assertFalse(update_check.is_newer("2.1.0-rc1", "2.1.0"))

    def test_malformed_does_not_raise(self):
        # non-numeric parts fall back to string order, never crash
        self.assertIsInstance(update_check.is_newer("abc", "2.0.0"), bool)


def _resp(body: str):
    m = mock.MagicMock()
    m.read.return_value = body.encode("utf-8")
    m.__enter__.return_value = m
    m.__exit__.return_value = False
    return m


class TestFetchLatest(unittest.TestCase):
    def test_success_strips_v_prefix(self):
        with mock.patch.object(update_check.urllib.request, "urlopen",
                               return_value=_resp(json.dumps({"tag_name": "v2.3.4"}))):
            self.assertEqual(update_check.fetch_latest_version(), "2.3.4")

    def test_success_without_prefix(self):
        with mock.patch.object(update_check.urllib.request, "urlopen",
                               return_value=_resp(json.dumps({"tag_name": "2.3.4"}))):
            self.assertEqual(update_check.fetch_latest_version(), "2.3.4")

    def test_missing_tag(self):
        with mock.patch.object(update_check.urllib.request, "urlopen",
                               return_value=_resp(json.dumps({"name": "x"}))):
            self.assertIsNone(update_check.fetch_latest_version())

    def test_bad_json(self):
        with mock.patch.object(update_check.urllib.request, "urlopen",
                               return_value=_resp("not json")):
            self.assertIsNone(update_check.fetch_latest_version())

    def test_network_error(self):
        with mock.patch.object(update_check.urllib.request, "urlopen",
                               side_effect=OSError("timeout")):
            self.assertIsNone(update_check.fetch_latest_version())


class TestCheckForUpdate(unittest.TestCase):
    def test_returns_version_when_newer(self):
        with mock.patch.object(update_check, "fetch_latest_version", return_value="9.9.9"), \
             mock.patch.object(update_check, "current_version", return_value="2.0.0"):
            self.assertEqual(update_check.check_for_update(), "9.9.9")

    def test_none_when_equal(self):
        with mock.patch.object(update_check, "fetch_latest_version", return_value="2.0.0"), \
             mock.patch.object(update_check, "current_version", return_value="2.0.0"):
            self.assertIsNone(update_check.check_for_update())

    def test_none_when_older(self):
        with mock.patch.object(update_check, "fetch_latest_version", return_value="1.0.0"), \
             mock.patch.object(update_check, "current_version", return_value="2.0.0"):
            self.assertIsNone(update_check.check_for_update())

    def test_none_when_fetch_fails(self):
        with mock.patch.object(update_check, "fetch_latest_version", return_value=None):
            self.assertIsNone(update_check.check_for_update())


if __name__ == "__main__":
    unittest.main()
