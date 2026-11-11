"""Routes for opening uploaded JT models in Teamcenter Visualization."""

import uuid

from flask import Blueprint, current_app, jsonify
from werkzeug.utils import secure_filename

from ..services.teamcenter_visualization import open_file_in_visualization
from ..utils.uploads import check_upload

teamcenter_visualization_bp = Blueprint("teamcenter_visualization", __name__)


@teamcenter_visualization_bp.post("/add-to-teamcenter-visualization")
def add_to_teamcenter_visualization():
    file, bad = check_upload()
    if bad:
        return bad

    folder = current_app.config["UPLOADS_DIR"] / "teamcenter_visualization" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    destination = folder / secure_filename(file.filename)
    file.save(destination)

    try:
        open_file_in_visualization(destination, open_in_new_document=True)
        return jsonify(ok=True, path=str(destination), new_tab=True)
    except Exception as error:
        current_app.logger.exception("Open in Teamcenter Visualization failed")
        return jsonify(
            error=(
                "Could not open the JT file in Teamcenter Visualization: "
                f"{type(error).__name__}: {error}"
            )
        ), 500
