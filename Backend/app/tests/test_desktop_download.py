import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import webview

from Desktop_app import DesktopApi


class DesktopDownloadTests(unittest.TestCase):
    def test_download_prompts_for_save_location_and_saves_server_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "assembly.jt"
            window = Mock()
            window.create_file_dialog.return_value = [str(destination)]
            api = DesktopApi()
            api.window = window

            with (
                patch("Desktop_app.HOST", "127.0.0.1"),
                patch("Desktop_app.PORT", 5000),
                patch(
                    "Desktop_app.urllib.request.urlopen",
                    return_value=io.BytesIO(b"JT model"),
                ) as urlopen,
            ):
                result = api.download_file(12, "assembly.jt")

            self.assertEqual(destination.read_bytes(), b"JT model")
        self.assertEqual(
            result,
            {"cancelled": False, "filename": "assembly.jt"},
        )
        window.create_file_dialog.assert_called_once_with(
            webview.FileDialog.SAVE,
            save_filename="assembly.jt",
            file_types=("JT files (*.jt)",),
        )
        urlopen.assert_called_once_with(
            "http://127.0.0.1:5000/api/jt-files/12/download",
            timeout=60,
        )

    def test_cancelled_save_dialog_does_not_download(self):
        api = DesktopApi()
        api.window = Mock()
        api.window.create_file_dialog.return_value = None

        with patch("Desktop_app.urllib.request.urlopen") as urlopen:
            result = api.download_file(12, "assembly.jt")

        self.assertEqual(result, {"cancelled": True})
        urlopen.assert_not_called()

    def test_rejects_non_jt_filename_before_opening_dialog(self):
        api = DesktopApi()
        api.window = Mock()

        with self.assertRaisesRegex(ValueError, "valid JT filename"):
            api.download_file(12, "image.png")

        api.window.create_file_dialog.assert_not_called()
