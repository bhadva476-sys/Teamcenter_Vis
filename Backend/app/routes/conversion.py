"""JT conversion and inspection API routes."""

import io
import os
import shutil
import uuid
import zipfile
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from ..services.conversion import (
    MIMETYPES,
    NoPreviewDataError,
    convert_jt,
    file_digest,
    load_aspose,
)
from ..services.jt_probe import probe_jt
from ..utils.uploads import check_upload

conversion_bp = Blueprint("conversion", __name__)


@conversion_bp.post("/probe")
def probe():
    """Report material/color data found directly in an uploaded JT file."""
    file, bad = check_upload()
    if bad:
        return bad
    try:
        lines = probe_jt(file.read())
    except Exception as error:
        current_app.logger.exception("Probe failed")
        return Response(
            f"Probe failed: {type(error).__name__}: {error}",
            mimetype="text/plain",
            status=500,
        )
    return Response("\n".join(lines), mimetype="text/plain")


@conversion_bp.post("/inspect")
def inspect():
    """Return material properties that Aspose reads from an uploaded JT."""
    file, bad = check_upload()
    if bad:
        return bad
    a3d, error = load_aspose()
    if a3d is None:
        return jsonify(error=error), 500

    source = current_app.config["UPLOADS_DIR"] / f"{uuid.uuid4().hex}.jt"
    file.save(source)
    try:
        scene = a3d.Scene.from_file(str(source))
        materials = []

        def walk(node):
            for material in node.materials or []:
                info = {"node": node.name, "material": type(material).__name__}
                for attribute in ("diffuse_color", "albedo", "ambient_color"):
                    if hasattr(material, attribute):
                        info[attribute] = str(getattr(material, attribute))
                materials.append(info)
            for child in node.child_nodes:
                walk(child)

        walk(scene.root_node)
        return jsonify(material_count=len(materials), materials=materials[:50])
    except Exception as error:
        current_app.logger.exception("Inspect failed")
        return jsonify(error=str(error)), 500
    finally:
        source.unlink(missing_ok=True)


@conversion_bp.post("/convert")
def convert():
    file, bad = check_upload()
    if bad:
        return bad

    output_format = (
        request.args.get("format") or request.form.get("format") or "glb"
    ).lower()
    if output_format not in ("glb", "gltf"):
        return jsonify(error="format must be 'glb' or 'gltf'."), 400

    job_id = uuid.uuid4().hex
    uploads_dir = current_app.config["UPLOADS_DIR"]
    converted_dir = current_app.config["CONVERTED_DIR"]
    source = uploads_dir / f"{job_id}.jt"
    job_dir = converted_dir / f"job_{job_id}"
    job_dir.mkdir()
    stem = Path(secure_filename(file.filename)).stem or "model"
    file.save(source)

    try:
        convert_jt(source, job_dir / f"model.{output_format}")
        files = sorted(path for path in job_dir.rglob("*") if path.is_file())
        buffer = io.BytesIO()
        if len(files) == 1:
            buffer.write(files[0].read_bytes())
            download_name = f"{stem}.{output_format}"
            mimetype = MIMETYPES[output_format]
        else:
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in files:
                    archive_name = path.relative_to(job_dir).as_posix()
                    if archive_name == f"model.{output_format}":
                        archive_name = f"{stem}.{output_format}"
                    archive.write(path, archive_name)
            download_name = f"{stem}_gltf.zip"
            mimetype = MIMETYPES["zip"]
        buffer.seek(0)
    except Exception as error:
        current_app.logger.exception("Conversion failed")
        return jsonify(error=f"Conversion failed: {error}"), 500
    finally:
        source.unlink(missing_ok=True)
        shutil.rmtree(job_dir, ignore_errors=True)

    return send_file(
        buffer,
        mimetype=mimetype,
        as_attachment=True,
        download_name=download_name,
    )


@conversion_bp.post("/upload")
def upload():
    """Convert a JT to a cached GLB for the browser viewer."""
    file, bad = check_upload()
    if bad:
        return bad

    digest = file_digest(file)
    converted_dir = current_app.config["CONVERTED_DIR"]
    destination = converted_dir / f"{digest}.glb"
    if destination.exists() and destination.stat().st_size > 0:
        return jsonify(url=f"/models/{digest}.glb", cached=True)

    job_id = uuid.uuid4().hex
    source = current_app.config["UPLOADS_DIR"] / f"{job_id}.jt"
    temporary = converted_dir / f"{digest}.{job_id}.tmp.glb"
    file.save(source)

    try:
        convert_jt(source, temporary)
        os.replace(temporary, destination)
    except NoPreviewDataError:
        return jsonify(
            preview_available=False,
            message="No preview data is available for this JT file.",
        )
    except Exception as error:
        current_app.logger.exception("Conversion failed")
        return jsonify(error=f"Conversion failed: {error}"), 500
    finally:
        source.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)

    return jsonify(url=f"/models/{digest}.glb", cached=False)
