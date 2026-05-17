import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from thermalright_lcd_control.device_controller.display import asset_download


class TestDownloadBundledBackground(unittest.TestCase):
    def test_builds_url_from_dest_parent_folder_name(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            dest = Path(tmp_root) / "240320" / "a001.mp4"
            with patch("urllib.request.urlopen") as mock_urlopen, \
                    patch("shutil.copyfileobj"):
                mock_resp = MagicMock()
                mock_resp.status = 200
                mock_urlopen.return_value.__enter__.return_value = mock_resp
                asset_download.download_bundled_background(
                    "a001", dest, media_endpoint="https://example.test/tr/")
                called_url = mock_urlopen.call_args[0][0]
                self.assertEqual(called_url, "https://example.test/tr/bj240320/a001.mp4")


class TestEnsureBackgroundDownloaded(unittest.TestCase):
    def test_downloads_missing_bundled_mp4(self):
        with patch.object(asset_download, "download_bundled_background") as mock_dl, \
                patch.object(Path, "exists", return_value=False):
            asset_download.ensure_background_downloaded("/base/240320/a001.mp4")
            mock_dl.assert_called_once()
            self.assertEqual(mock_dl.call_args[0][0], "a001")

    def test_skips_existing_file(self):
        with patch.object(asset_download, "download_bundled_background") as mock_dl, \
                patch.object(Path, "exists", return_value=True):
            asset_download.ensure_background_downloaded("/base/240320/a001.mp4")
            mock_dl.assert_not_called()

    def test_skips_user_imported_background(self):
        with patch.object(asset_download, "download_bundled_background") as mock_dl, \
                patch.object(Path, "exists", return_value=False):
            asset_download.ensure_background_downloaded("/base/240320/user_a001.mp4")
            mock_dl.assert_not_called()

    def test_skips_non_mp4(self):
        with patch.object(asset_download, "download_bundled_background") as mock_dl, \
                patch.object(Path, "exists", return_value=False):
            asset_download.ensure_background_downloaded("/base/240320/a001.png")
            mock_dl.assert_not_called()

    def test_download_failure_is_swallowed(self):
        with patch.object(asset_download, "download_bundled_background",
                           side_effect=RuntimeError("boom")), \
                patch.object(Path, "exists", return_value=False):
            asset_download.ensure_background_downloaded("/base/240320/a001.mp4")  # no raise


if __name__ == "__main__":
    unittest.main()
