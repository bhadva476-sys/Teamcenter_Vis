from datetime import datetime
import unittest
from unittest.mock import Mock, patch

from app import create_app
from app.services.jt_file_uploads import (
    get_local_jt_file_path,
    get_local_jt_thumbnail_path,
)


class JTFileListTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "JT_WEBCLIENT_TABLE": "jtweb_client",
            }
        )
        self.client = self.app.test_client()

    def test_list_returns_thumbnail_url_without_exposing_server_paths(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [{"Field": "Name"}],
            [{
                "id": 12,
                "Name": "assembly.jt",
                "type": ".jt",
                "size": 4096,
                "createdat": datetime(2026, 10, 23, 12, 0, 0),
                "updatedat": datetime(2026, 10, 23, 12, 5, 0),
                "attribute_owner": "local-user",
                "Thumbnail_Location": "C:/ServerThumbnails/dev/preview.png",
            }],
        ]
        connection = Mock()
        connection.cursor.return_value = cursor

        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            response = self.client.get("/list")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "count": 1,
                "files": [
                    {
                        "id": 12,
                        "filename": "assembly.jt",
                        "type": ".jt",
                        "size": 4096,
                        "createdat": "2026-10-23T12:00:00",
                        "updatedat": "2026-10-23T12:05:00",
                        "attribute_owner": "local-user",
                        "thumbnail_url": "/api/jt-files/12/thumbnail",
                    }
                ],
            },
        )
        self.assertNotIn(b"must-not-be-returned", response.data)
        query, params = cursor.execute.call_args_list[-1].args
        self.assertIn("FROM `jtweb_client`", query)
        self.assertIn("`Thumbnail_Location`", query)
        self.assertIn("ORDER BY `id` DESC", query)
        self.assertIn("LIMIT %s", query)
        self.assertEqual(params, (100,))
        self.assertTrue(
            any(
                call.args[0].startswith(
                    "ALTER TABLE `jtweb_client` ADD COLUMN `Thumbnail_Location`"
                )
                for call in cursor.execute.call_args_list
            )
        )
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()
        response.close()

    def test_list_returns_empty_array_when_database_has_no_records(self):
        cursor = Mock()
        cursor.fetchall.return_value = []
        connection = Mock()
        connection.cursor.return_value = cursor

        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            response = self.client.get("/list")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"count": 0, "files": []})
        response.close()

    def test_list_reports_database_errors(self):
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            side_effect=RuntimeError("database unavailable"),
        ):
            response = self.client.get("/list")

        self.assertEqual(response.status_code, 503)
        self.assertIn("MySQL", response.json["error"])
        response.close()

    def test_my_files_path_lookup_is_limited_to_local_owner(self):
        cursor = Mock()
        cursor.fetchone.return_value = {"file_location": "C:/ServerUploads/model.jt"}
        connection = Mock()
        connection.cursor.return_value = cursor

        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            with self.app.app_context():
                path = get_local_jt_file_path(12)

        self.assertEqual(path, "C:/ServerUploads/model.jt")
        query, params = cursor.execute.call_args.args
        self.assertIn("`attribute_owner` = %s", query)
        self.assertEqual(params, (12, "local-user"))
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_thumbnail_path_lookup_is_limited_to_local_owner(self):
        cursor = Mock()
        cursor.fetchone.return_value = {
            "Thumbnail_Location": "C:/ServerThumbnails/dev/preview.png"
        }
        connection = Mock()
        connection.cursor.return_value = cursor

        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            with self.app.app_context():
                path = get_local_jt_thumbnail_path(12)

        self.assertEqual(path, "C:/ServerThumbnails/dev/preview.png")
        query, params = cursor.execute.call_args.args
        self.assertIn("`Thumbnail_Location`", query)
        self.assertIn("`attribute_owner` = %s", query)
        self.assertEqual(params, (12, "local-user"))
