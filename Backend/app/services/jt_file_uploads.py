"""Persist original JT uploads and register their metadata in MySQL."""

import logging
import re
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

CHUNK_SIZE = 1024 * 1024
LOCAL_OWNER = "local-user"
REQUIRED_COLUMNS = {
    "name": "`Name` VARCHAR(255) NOT NULL DEFAULT ''",
    "type": "`type` VARCHAR(16) NOT NULL DEFAULT ''",
    "file_location": "`file_location` VARCHAR(2048) NOT NULL DEFAULT ''",
    "size": "`size` BIGINT UNSIGNED NOT NULL DEFAULT 0",
    "createdat": "`createdat` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updatedat": (
        "`updatedat` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP"
    ),
    "attribute_owner": "`attribute_owner` VARCHAR(255) NOT NULL DEFAULT 'local-user'",
    "thumbnail_location": "`Thumbnail_Location` VARCHAR(2048) NULL DEFAULT NULL",
}
THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class JTFileValidationError(ValueError):
    """An uploaded JT file is empty or exceeds the configured limit."""


class JTFileDatabaseError(RuntimeError):
    """The JT file metadata could not be registered in MySQL."""


def _original_filename(filename):
    return (filename or "").replace("\\", "/").rsplit("/", 1)[-1]


def save_jt_file(upload, directory: Path, max_file_size: int):
    """Save a validated JT file under a unique name, without overwriting files."""
    original_name = _original_filename(upload.filename)
    if not original_name.lower().endswith(".jt"):
        raise JTFileValidationError("Only .jt files are allowed.")
    if len(original_name) > 255:
        raise JTFileValidationError("The JT filename must be 255 characters or fewer.")

    stored_name = secure_filename(original_name) or "upload.jt"
    if not stored_name.lower().endswith(".jt"):
        stored_name += ".jt"
    if len(stored_name) > 120:
        stored_name = f"{stored_name[:-3][:117]}{stored_name[-3:]}"

    directory.mkdir(parents=True, exist_ok=True)
    destination = None
    for _ in range(10):
        candidate = directory / f"{uuid.uuid4().hex}_{stored_name[:120]}"
        try:
            output = candidate.open("xb")
            destination = candidate
            break
        except FileExistsError:
            continue
    else:
        raise OSError("Could not allocate a unique filename for the JT upload.")

    size = 0
    try:
        with output:
            while True:
                chunk = upload.stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_file_size:
                    raise JTFileValidationError(
                        f"JT file exceeds the {max_file_size}-byte upload limit."
                    )
                output.write(chunk)

        if size == 0:
            raise JTFileValidationError("The JT file is empty.")
        return original_name, destination.resolve(), size
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def save_thumbnail(upload, directory: Path, max_file_size: int):
    """Save a PNG, JPEG, or WebP thumbnail under a unique name."""
    extension = Path(_original_filename(upload.filename)).suffix.lower()
    if extension not in THUMBNAIL_EXTENSIONS:
        raise JTFileValidationError("Thumbnail must be a PNG, JPG, or WebP image.")

    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{uuid.uuid4().hex}{extension}"
    signature = bytearray()
    size = 0

    try:
        with destination.open("xb") as output:
            while True:
                chunk = upload.stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_file_size:
                    raise JTFileValidationError(
                        f"Thumbnail exceeds the {max_file_size}-byte upload limit."
                    )
                if len(signature) < 12:
                    signature.extend(chunk[: 12 - len(signature)])
                output.write(chunk)

        valid_png = signature.startswith(b"\x89PNG\r\n\x1a\n")
        valid_jpeg = signature.startswith(b"\xff\xd8\xff")
        valid_webp = signature[:4] == b"RIFF" and signature[8:12] == b"WEBP"
        if size == 0:
            raise JTFileValidationError("The thumbnail image is empty.")
        if not (valid_png or valid_jpeg or valid_webp):
            raise JTFileValidationError(
                "Thumbnail contents must be a valid PNG, JPG, or WebP image."
            )
        return destination.resolve()
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _connect_to_database():
    import mysql.connector

    return mysql.connector.connect(
        host=current_app.config["DB_HOST"],
        port=current_app.config["DB_PORT"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PASSWORD"],
        database=current_app.config["DB_NAME"],
        connection_timeout=10,
    )


def _validated_table_name():
    table_name = current_app.config["JT_WEBCLIENT_TABLE"]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise JTFileDatabaseError("JT_WEBCLIENT_TABLE must be a simple SQL identifier.")
    return f"`{table_name}`"


def _ensure_thumbnail_column(cursor):
    """Add the optional thumbnail path to existing tables without changing data."""
    table = _validated_table_name()
    cursor.execute(f"SHOW COLUMNS FROM {table}")
    columns = cursor.fetchall()
    if not any(
        column["Field"].casefold() == "thumbnail_location"
        for column in columns
    ):
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN "
            "`Thumbnail_Location` VARCHAR(2048) NULL DEFAULT NULL"
        )


def _ensure_table(cursor):
    table = _validated_table_name()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `Name` VARCHAR(255) NOT NULL,
            `type` VARCHAR(16) NOT NULL,
            `file_location` VARCHAR(2048) NOT NULL,
            `size` BIGINT UNSIGNED NOT NULL,
            `createdat` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updatedat` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            `attribute_owner` VARCHAR(255) NOT NULL DEFAULT 'local-user',
            `Thumbnail_Location` VARCHAR(2048) NULL DEFAULT NULL
        ) ENGINE=InnoDB
        """
    )
    cursor.execute(f"SHOW COLUMNS FROM {table}")
    columns = cursor.fetchall()
    column_by_name = {column["Field"].casefold(): column for column in columns}

    if "id" not in column_by_name:
        if any(column["Key"] == "PRI" for column in columns):
            raise JTFileDatabaseError(
                "jtweb_client has a different primary key; refusing an unsafe migration."
            )
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN "
            "`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST"
        )
    else:
        id_column = column_by_name["id"]
        id_extra = str(id_column.get("Extra") or "").lower()
        if id_column["Key"] != "PRI" or "auto_increment" not in id_extra:
            raise JTFileDatabaseError(
                "jtweb_client.id must be an auto-increment primary key; "
                "refusing an unsafe migration."
            )

    for name, definition in REQUIRED_COLUMNS.items():
        if name not in column_by_name:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def insert_jt_file_record(
    filename, file_location, size, file_type=".jt", thumbnail_location=None
):
    """Ensure the expected schema exists and insert metadata using bound values."""
    connection = None
    cursor = None
    try:
        connection = _connect_to_database()
        cursor = connection.cursor(dictionary=True)
        _ensure_table(cursor)
        table_name = current_app.config["JT_WEBCLIENT_TABLE"]
        cursor.execute(
            f"""
            INSERT INTO `{table_name}`
                (`Name`, `type`, `file_location`, `size`, `attribute_owner`,
                 `Thumbnail_Location`)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                filename,
                file_type,
                str(file_location),
                size,
                LOCAL_OWNER,
                str(thumbnail_location) if thumbnail_location else None,
            ),
        )
        record_id = cursor.lastrowid
        connection.commit()
        return record_id
    except JTFileDatabaseError:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                current_app.logger.exception("MySQL rollback failed")
        raise
    except Exception as error:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                current_app.logger.exception("MySQL rollback failed")
        current_app.logger.exception("JT upload metadata insert failed")
        raise JTFileDatabaseError(
            "Could not connect to MySQL or register the JT file metadata."
        ) from error
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL cursor")
        if connection is not None:
            try:
                connection.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL connection")


def list_jt_file_records(limit=100):
    """Return the newest JT metadata records, including their server file paths."""
    connection = None
    cursor = None
    try:
        connection = _connect_to_database()
        cursor = connection.cursor(dictionary=True)
        table = _validated_table_name()
        _ensure_thumbnail_column(cursor)
        cursor.execute(
            f"""
            SELECT `id`, `Name`, `type`, `size`, `createdat`, `updatedat`,
                   `attribute_owner`, `Thumbnail_Location`
            FROM {table}
            ORDER BY `id` DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "filename": row["Name"],
                "type": row["type"],
                "size": row["size"],
                "createdat": (
                    row["createdat"].isoformat()
                    if row.get("createdat") is not None
                    else None
                ),
                "updatedat": (
                    row["updatedat"].isoformat()
                    if row.get("updatedat") is not None
                    else None
                ),
                "attribute_owner": row["attribute_owner"],
                "thumbnail_url": (
                    f"/api/jt-files/{row['id']}/thumbnail"
                    if row.get("Thumbnail_Location")
                    else None
                ),
            }
            for row in rows
        ]
    except JTFileDatabaseError:
        raise
    except Exception as error:
        current_app.logger.exception("Could not list JT upload records")
        raise JTFileDatabaseError(
            "Could not connect to MySQL or load JT file metadata."
        ) from error
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL cursor")
        if connection is not None:
            try:
                connection.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL connection")


def get_local_jt_file_path(record_id):
    """Return the stored path for a local-user record, or None when absent."""
    connection = None
    cursor = None
    try:
        connection = _connect_to_database()
        cursor = connection.cursor(dictionary=True)
        table = _validated_table_name()
        cursor.execute(
            f"""
            SELECT `file_location`
            FROM {table}
            WHERE `id` = %s AND `attribute_owner` = %s
            """,
            (record_id, LOCAL_OWNER),
        )
        row = cursor.fetchone()
        return row["file_location"] if row else None
    except JTFileDatabaseError:
        raise
    except Exception as error:
        current_app.logger.exception("Could not load JT file path")
        raise JTFileDatabaseError(
            "Could not connect to MySQL or load the JT file."
        ) from error
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL cursor")
        if connection is not None:
            try:
                connection.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL connection")


def get_local_jt_thumbnail_path(record_id):
    """Return the stored thumbnail path for a local-user record, if present."""
    connection = None
    cursor = None
    try:
        connection = _connect_to_database()
        cursor = connection.cursor(dictionary=True)
        table = _validated_table_name()
        cursor.execute(
            f"""
            SELECT `Thumbnail_Location`
            FROM {table}
            WHERE `id` = %s AND `attribute_owner` = %s
            """,
            (record_id, LOCAL_OWNER),
        )
        row = cursor.fetchone()
        return row["Thumbnail_Location"] if row else None
    except JTFileDatabaseError:
        raise
    except Exception as error:
        current_app.logger.exception("Could not load JT thumbnail path")
        raise JTFileDatabaseError(
            "Could not connect to MySQL or load the JT thumbnail."
        ) from error
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL cursor")
        if connection is not None:
            try:
                connection.close()
            except Exception:
                logging.getLogger(__name__).exception("Could not close MySQL connection")
