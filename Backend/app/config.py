"""Runtime configuration and paths for the local JT converter."""

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
APP_ENV = os.environ.get("APP_ENV", "dev").lower()

if APP_ENV not in ("dev", "prod"):
    raise ValueError("APP_ENV must be 'dev' or 'prod'")

ENV_FILE = PROJECT_DIR / "config" / f".env.{APP_ENV}"
load_dotenv(ENV_FILE, override=False)
print("ENV_FILE:", ENV_FILE, "exists:", ENV_FILE.exists(), "DB_USER:", repr(os.environ.get("DB_USER")), flush=True)


def _configured_path(variable, default):
    value = os.environ.get(variable)
    if not value:
        return Path(default).resolve()
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path.resolve()


UPLOADS_DIR = _configured_path("JT_UPLOADS_DIR", APP_DIR / "uploads")
CONVERTED_DIR = _configured_path("JT_CONVERTED_DIR", APP_DIR / "converted")
SERVER_UPLOADS_DIR = _configured_path(
    "JT_SERVER_UPLOADS_DIR", BACKEND_DIR / "ServerUploads" / APP_ENV
)
SERVER_THUMBNAILS_DIR = _configured_path(
    "JT_SERVER_THUMBNAILS_DIR", BACKEND_DIR / "ServerThumbnails" / APP_ENV
)
MAX_CONTENT_LENGTH = int(
    os.environ.get("MAX_CONTENT_LENGTH", str(200 * 1024 * 1024))
)
MAX_JT_FILE_SIZE = MAX_CONTENT_LENGTH
MAX_THUMBNAIL_SIZE = int(
    os.environ.get("MAX_THUMBNAIL_SIZE", str(5 * 1024 * 1024))
)
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "PLM")
JT_WEBCLIENT_TABLE = os.environ.get("JT_WEBCLIENT_TABLE", "jtweb_client")
