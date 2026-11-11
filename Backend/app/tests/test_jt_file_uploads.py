from io import BytesIO
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app import create_app


class FakeCursor:
    def __init__(self, fail_insert=False, columns=None):
        self.fail_insert = fail_insert
        self.lastrowid = 71
        self.executed = []
        self.closed = False
        self.columns = columns or [
            {"Field": "id", "Key": "PRI", "Extra": "auto_increment"},
            {"Field": "Name", "Key": "", "Extra": ""},
            {"Field": "type", "Key": "", "Extra": ""},
            {"Field": "file_location", "Key": "", "Extra": ""},
            {"Field": "size", "Key": "", "Extra": ""},
            {"Field": "createdat", "Key": "", "Extra": ""},
            {"Field": "updatedat", "Key": "", "Extra": ""},
            {"Field": "attribute_owner", "Key": "", "Extra": ""},
            {"Field": "Thumbnail_Location", "Key": "", "Extra": ""},
        ]

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if query.lstrip().startswith("INSERT") and self.fail_insert:
            raise RuntimeError("simulated insert failure")

    def fetchall(self):
        return self.columns

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, fail_insert=False, columns=None):
        self.fake_cursor = FakeCursor(fail_insert=fail_insert, columns=columns)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, dictionary=False):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class JTFileUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(__file__).parent / "temp" / uuid4().hex
        self.upload_dir = self.temp_dir / "ServerUploads"
        self.thumbnail_dir = self.temp_dir / "ServerThumbnails" / "dev"
        self.app = create_app(
            {
                "TESTING": True,
                "UPLOADS_DIR": self.temp_dir / "uploads",
                "CONVERTED_DIR": self.temp_dir / "converted",
                "SERVER_UPLOADS_DIR": self.upload_dir,
                "SERVER_THUMBNAILS_DIR": self.thumbnail_dir,
                "MAX_THUMBNAIL_SIZE": 1024,
                "MAX_JT_FILE_SIZE": 4,
                "MAX_CONTENT_LENGTH": 1024 * 1024,
                "DB_HOST": "localhost",
                "DB_PORT": 3306,
                "DB_USER": "test-user",
                "DB_PASSWORD": "",
                "DB_NAME": "PLM",
                "JT_WEBCLIENT_TABLE": "jtweb_client_test",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def upload(
        self, content=b"JT!!", filename="assembly.jt", thumbnail=None,
        preview_available=None
    ):
        data = {"file": (BytesIO(content), filename)}
        if preview_available is not None:
            data["preview_available"] = str(preview_available).lower()
        if thumbnail is not None:
            thumbnail_content, thumbnail_filename = thumbnail
            data["thumbnail"] = (BytesIO(thumbnail_content), thumbnail_filename)
        return self.client.post(
            "/api/jt-files/upload",
            data=data,
            content_type="multipart/form-data",
        )

    def test_upload_saves_file_and_inserts_metadata(self):
        connection = FakeConnection()
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            response = self.upload()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json,
            {
                "status": "success",
                "id": 71,
                "filename": "assembly.jt",
                "file_size": 4,
            },
        )
        insert = next(
            item
            for item in connection.fake_cursor.executed
            if item[0].lstrip().startswith("INSERT")
        )
        filename, file_type, file_location, size, owner, thumbnail_location = insert[1]
        saved_file = Path(file_location)
        self.assertEqual(
            (filename, file_type, size, owner),
            ("assembly.jt", ".jt", 4, "local-user"),
        )
        self.assertEqual(saved_file.read_bytes(), b"JT!!")
        self.assertIsNone(thumbnail_location)
        self.assertTrue(
            any(
                "CREATE TABLE IF NOT EXISTS `jtweb_client_test`" in query
                for query, _ in connection.fake_cursor.executed
            )
        )
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        self.assertTrue(connection.fake_cursor.closed)
        response.close()

    def test_invalid_extension_is_rejected(self):
        response = self.upload(filename="model.txt")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "Only .jt files are allowed.")
        self.assertFalse(self.upload_dir.exists() and any(self.upload_dir.iterdir()))
        response.close()

    def test_empty_file_is_rejected(self):
        response = self.upload(content=b"")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "The JT file is empty.")
        self.assertFalse(self.upload_dir.exists() and any(self.upload_dir.iterdir()))
        response.close()

    def test_file_over_configured_size_limit_is_rejected(self):
        response = self.upload(content=b"JT!!!")

        self.assertEqual(response.status_code, 400)
        self.assertIn("upload limit", response.json["error"])
        self.assertFalse(self.upload_dir.exists() and any(self.upload_dir.iterdir()))
        response.close()

    def test_repeated_original_filename_creates_distinct_saved_files(self):
        connections = [FakeConnection(), FakeConnection()]
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            side_effect=connections,
        ):
            first = self.upload()
            second = self.upload()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        first_path = Path(
            next(
                item[1]
                for item in connections[0].fake_cursor.executed
                if item[0].lstrip().startswith("INSERT")
            )[2]
        )
        second_path = Path(
            next(
                item[1]
                for item in connections[1].fake_cursor.executed
                if item[0].lstrip().startswith("INSERT")
            )[2]
        )
        self.assertNotEqual(first_path, second_path)
        self.assertTrue(first_path.exists())
        self.assertTrue(second_path.exists())
        first.close()
        second.close()

    def test_database_connection_failure_removes_only_new_file(self):
        preexisting = self.upload_dir / "keep-this-file.jt"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        preexisting.write_bytes(b"existing")
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            side_effect=RuntimeError("database unavailable"),
        ):
            response = self.upload()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(preexisting.read_bytes(), b"existing")
        self.assertEqual(list(self.upload_dir.iterdir()), [preexisting])
        response.close()

    def test_database_insert_failure_rolls_back_and_removes_new_file(self):
        connection = FakeConnection(fail_insert=True)
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            response = self.upload()

        self.assertEqual(response.status_code, 503)
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)
        self.assertFalse(any(self.upload_dir.iterdir()))
        response.close()

    def test_metadata_insert_uses_parameterized_values(self):
        connection = FakeConnection()
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            self.upload(filename="model'; DROP TABLE jtweb_client;--.jt")

        insert_query, parameters = next(
            item
            for item in connection.fake_cursor.executed
            if item[0].lstrip().startswith("INSERT")
        )
        self.assertIn("VALUES (%s, %s, %s, %s, %s, %s)", insert_query)
        self.assertEqual(parameters[0], "model'; DROP TABLE jtweb_client;--.jt")

    def test_existing_table_is_migrated_additively(self):
        connection = FakeConnection(
            columns=[
                {"Field": "id", "Key": "PRI", "Extra": "auto_increment"},
                {"Field": "Name", "Key": "", "Extra": ""},
            ]
        )
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            response = self.upload()

        self.assertEqual(response.status_code, 201)
        alterations = [
            query
            for query, _ in connection.fake_cursor.executed
            if query.startswith("ALTER TABLE")
        ]
        self.assertEqual(len(alterations), 7)
        self.assertTrue(all("ADD COLUMN" in query for query in alterations))
        self.assertFalse(any("DROP" in query for query, _ in connection.fake_cursor.executed))
        response.close()

    def test_previewed_upload_requires_thumbnail(self):
        response = self.upload(preview_available=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose a thumbnail", response.json["error"])
        self.assertFalse(self.upload_dir.exists() and any(self.upload_dir.iterdir()))
        response.close()

    def test_thumbnail_is_saved_and_registered_in_mysql(self):
        connection = FakeConnection()
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            response = self.upload(
                preview_available=True,
                thumbnail=(b"\x89PNG\r\n\x1a\nimage", "preview.png"),
            )

        self.assertEqual(response.status_code, 201)
        insert_query, parameters = next(
            item
            for item in connection.fake_cursor.executed
            if item[0].lstrip().startswith("INSERT")
        )
        self.assertIn("`Thumbnail_Location`", insert_query)
        thumbnail_path = Path(parameters[5])
        self.assertEqual(thumbnail_path.parent, self.thumbnail_dir)
        self.assertEqual(thumbnail_path.read_bytes(), b"\x89PNG\r\n\x1a\nimage")
        response.close()

    def test_invalid_thumbnail_is_rejected_without_leaving_jt_file(self):
        response = self.upload(
            preview_available=True,
            thumbnail=(b"not an image", "preview.png"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid PNG", response.json["error"])
        self.assertFalse(self.upload_dir.exists() and any(self.upload_dir.iterdir()))
        response.close()

    def test_unsafe_configured_table_name_is_rejected(self):
        self.app.config["JT_WEBCLIENT_TABLE"] = "jtweb_client; DROP TABLE users"
        connection = FakeConnection()
        with patch(
            "app.services.jt_file_uploads._connect_to_database",
            return_value=connection,
        ):
            response = self.upload()

        self.assertEqual(response.status_code, 503)
        self.assertFalse(connection.fake_cursor.executed)
        self.assertFalse(any(self.upload_dir.iterdir()))
        response.close()
