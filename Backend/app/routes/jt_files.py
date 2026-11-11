
"""API endpoints for storing JT files and registering their metadata."""

from pathlib import Path
from app.services.visualization_watcher import (
    open_file_in_visualization
)

from flask import Blueprint, current_app, jsonify, request, send_file

from ..services.jt_file_uploads import (
    JTFileDatabaseError,
    JTFileValidationError,
    get_local_jt_file_path,
    get_local_jt_thumbnail_path,
    insert_jt_file_record,
    list_jt_file_records,
    save_jt_file,
    save_thumbnail,
)

from ..utils.uploads import check_upload


jt_files_bp = Blueprint(
    "jt_files",
    __name__,
    url_prefix="/api/jt-files"
)

jt_file_list_bp = Blueprint(
    "jt_file_list",
    __name__
)


@jt_file_list_bp.get("/list")
def list_jt_files():
    try:
        files = list_jt_file_records()

    except JTFileDatabaseError:
        return jsonify(
            error="Could not load uploaded JT file information from MySQL."
        ), 503

    return jsonify(
        files=files,
        count=len(files)
    )


# ================= DOWNLOAD JT FILE =================

@jt_files_bp.get("/<int:file_id>/download")
def download_jt_file(file_id):

    try:
        stored_path = get_local_jt_file_path(file_id)

    except JTFileDatabaseError:
        return jsonify(
            error="Could not load the JT file information from MySQL."
        ), 503

    if not stored_path:
        return jsonify(
            error="File record was not found."
        ), 404

    try:
        upload_root = Path(
            current_app.config["SERVER_UPLOADS_DIR"]
        ).resolve()

        file_path = Path(stored_path).resolve(strict=True)

        # Allow files only inside ServerUploads
        file_path.relative_to(upload_root)

    except (OSError, RuntimeError, TypeError, ValueError):
        return jsonify(
            error="The file is missing from the server uploads folder."
        ), 404

    if not file_path.is_file():
        return jsonify(
            error="The stored record is not an available file."
        ), 404

    # Download debugging logs
    print(f"[DOWNLOAD] File ID: {file_id}", flush=True)
    print(f"[DOWNLOAD] File Path: {file_path}", flush=True)
    print(f"[DOWNLOAD] File Exists: {file_path.exists()}", flush=True)
    print(f"[DOWNLOAD] File Size: {file_path.stat().st_size} bytes", flush=True)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_path.name
    )


@jt_files_bp.get("/<int:file_id>/thumbnail")
def get_jt_file_thumbnail(file_id):
    try:
        stored_path = get_local_jt_thumbnail_path(file_id)
    except JTFileDatabaseError:
        return jsonify(error="Could not load the thumbnail information from MySQL."), 503

    if not stored_path:
        return jsonify(error="Thumbnail was not found."), 404

    try:
        thumbnail_root = Path(
            current_app.config["SERVER_THUMBNAILS_DIR"]
        ).resolve()
        thumbnail_path = Path(stored_path).resolve(strict=True)
        thumbnail_path.relative_to(thumbnail_root)
    except (OSError, RuntimeError, TypeError, ValueError):
        return jsonify(error="The thumbnail is missing from the server folder."), 404

    if not thumbnail_path.is_file() or thumbnail_path.suffix.lower() not in {
        ".jpg", ".jpeg", ".png", ".webp"
    }:
        return jsonify(error="The stored thumbnail is not an available image."), 404

    return send_file(thumbnail_path, conditional=True)


# ================= UPLOAD JT FILE =================

@jt_files_bp.post("/upload")
def upload_jt_file():

    upload, bad = check_upload()

    if bad:
        return bad

    thumbnail_upload = request.files.get("thumbnail")
    preview_available = request.form.get("preview_available", "").lower() == "true"
    if preview_available and (
        thumbnail_upload is None or not thumbnail_upload.filename
    ):
        return jsonify(
            error="Choose a thumbnail image before uploading this previewed model."
        ), 400

    try:
        filename, saved_path, size = save_jt_file(
            upload,
            current_app.config["SERVER_UPLOADS_DIR"],
            current_app.config["MAX_JT_FILE_SIZE"],
        )

    except JTFileValidationError as error:
        return jsonify(error=str(error)), 400

    thumbnail_path = None
    if thumbnail_upload is not None and thumbnail_upload.filename:
        try:
            thumbnail_path = save_thumbnail(
                thumbnail_upload,
                current_app.config["SERVER_THUMBNAILS_DIR"],
                current_app.config["MAX_THUMBNAIL_SIZE"],
            )
        except JTFileValidationError as error:
            saved_path.unlink(missing_ok=True)
            return jsonify(error=str(error)), 400
        except OSError:
            saved_path.unlink(missing_ok=True)
            current_app.logger.exception("Could not save JT thumbnail")
            return jsonify(error="Could not save the thumbnail image."), 500

    try:
        record_id = insert_jt_file_record(
            filename=filename,
            file_location=saved_path,
            size=size,
            thumbnail_location=thumbnail_path,
        )

    except JTFileDatabaseError:
        for path in (saved_path, thumbnail_path):
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    current_app.logger.exception(
                        "Could not remove upload after metadata registration failed"
                    )

        return jsonify(
            error=(
                "The JT file was saved temporarily but could not be registered in "
                "MySQL. Check the database connection and schema, then try again."
            )
        ), 503

    return jsonify(
        status="success",
        id=record_id,
        filename=filename,
        file_size=size,
    ), 201


# ============ OPEN IN TEAMCENTER VISUALIZATION ============

@jt_files_bp.post("/<int:file_id>/open-in-teamcenter-visualization")
def open_registered_jt_file(file_id):

    print(
        f"Request to open registered JT file with ID: {file_id}",
        flush=True
    )

    try:
        stored_path = get_local_jt_file_path(file_id)

    except JTFileDatabaseError:
        return jsonify(
            error="Could not load the JT file information from MySQL."
        ), 503

    if not stored_path:
        return jsonify(
            error="My Files record was not found."
        ), 404

    try:
        upload_root = Path(
            current_app.config["SERVER_UPLOADS_DIR"]
        ).resolve()

        file_path = Path(stored_path).resolve(strict=True)
        file_path.relative_to(upload_root)

    except (OSError, RuntimeError, TypeError, ValueError):
        return jsonify(
            error="The JT file is missing from the server uploads folder."
        ), 404

    if not file_path.is_file() or file_path.suffix.lower() != ".jt":
        return jsonify(
            error="The stored record is not an available JT file."
        ), 404

    try:
        open_file_in_visualization(file_path)

        return jsonify(
            ok=True,
            filename=file_path.name,
            new_tab=True
        )

    except Exception as error:
        print(
            f"Error occurred while opening JT file in Teamcenter Visualization: "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        current_app.logger.exception(
            "Open registered JT file in Teamcenter Visualization failed"
        )

        return jsonify(
            error=(
                f"Could not open the JT file in Teamcenter Visualization: "
                f"{type(error).__name__}: {error}"
            )
        ), 500
