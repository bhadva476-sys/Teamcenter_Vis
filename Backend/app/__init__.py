"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask

from .config import (
    CONVERTED_DIR,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    JT_WEBCLIENT_TABLE,
    MAX_CONTENT_LENGTH,
    MAX_JT_FILE_SIZE,
    MAX_THUMBNAIL_SIZE,
    SERVER_UPLOADS_DIR,
    SERVER_THUMBNAILS_DIR,
    UPLOADS_DIR,
)

from .routes.conversion import conversion_bp
from .routes.jt_files import jt_file_list_bp, jt_files_bp
from .routes.main import main_bp
from .routes.teamcenter_visualization import teamcenter_visualization_bp
from .utils.errors import register_error_handlers


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static")
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
        MAX_JT_FILE_SIZE=MAX_JT_FILE_SIZE,
        UPLOADS_DIR=UPLOADS_DIR,
        CONVERTED_DIR=CONVERTED_DIR,
        SERVER_UPLOADS_DIR=SERVER_UPLOADS_DIR,
        SERVER_THUMBNAILS_DIR=SERVER_THUMBNAILS_DIR,
        MAX_THUMBNAIL_SIZE=MAX_THUMBNAIL_SIZE,
        DB_HOST=DB_HOST,
        DB_PORT=DB_PORT,
        DB_USER=DB_USER,
        DB_PASSWORD=DB_PASSWORD,
        DB_NAME=DB_NAME,
        JT_WEBCLIENT_TABLE=JT_WEBCLIENT_TABLE,
    )
    if test_config is not None:
        app.config.update(test_config)

    for key in (
        "UPLOADS_DIR",
        "CONVERTED_DIR",
        "SERVER_UPLOADS_DIR",
        "SERVER_THUMBNAILS_DIR",
    ):
        directory = Path(app.config[key])
        directory.mkdir(parents=True, exist_ok=True)
        app.config[key] = directory

    register_error_handlers(app)
    app.register_blueprint(main_bp)
    app.register_blueprint(conversion_bp)
    app.register_blueprint(teamcenter_visualization_bp)
    app.register_blueprint(jt_files_bp)
    app.register_blueprint(jt_file_list_bp)

    @app.after_request
    def add_cors(response):
        origin = os.environ.get("CORS_ORIGIN")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        return response

    return app
