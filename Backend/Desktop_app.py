import ctypes
import os
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import webview
from waitress import serve
from werkzeug.utils import secure_filename

from app import create_app
from app.config import HOST, PORT

flask_app = create_app()


def local_host():
    return "127.0.0.1" if HOST in ("", "0.0.0.0", "::") else HOST


APP_URL = f"http://{local_host()}:{PORT}/"

# Works on pywebview 4.x and 5.x
SAVE_DIALOG = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG


def download_file(file_id, filename):
    print("download_file called:", file_id, filename, flush=True)

    try:
        file_id = int(file_id)
        if file_id < 1:
            raise ValueError
    except (TypeError, ValueError):
        return {"success": False, "error": "Invalid JT file ID."}

    filename = secure_filename(Path(str(filename).replace("\\", "/")).name)
    if not filename or Path(filename).suffix.lower() != ".jt":
        return {"success": False, "error": "A valid JT filename is required."}

    # 1. Ask the user where to save
    selected = webview.windows[0].create_file_dialog(
        SAVE_DIALOG,
        directory=str(Path.home() / "Downloads"),  # starting folder only
        save_filename=filename,
        file_types=("JT files (*.jt)", "All files (*.*)"),
    )
    if not selected:
        return {"success": False, "cancelled": True}

    save_path = selected[0] if isinstance(selected, (list, tuple)) else selected
    destination = Path(save_path)
    if destination.suffix.lower() != ".jt":
        destination = destination.with_suffix(".jt")

    # 2. Download from the local Flask server into a .part file, then rename
    download_url = f"http://{local_host()}:{PORT}/api/jt-files/{file_id}/download"
    temporary_path = None
    try:
        print("[DOWNLOAD] Requesting:", download_url, flush=True)
        with urllib.request.urlopen(download_url, timeout=60) as response:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".part",
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                shutil.copyfileobj(response, output)

        os.replace(temporary_path, destination)
        temporary_path = None  # renamed, nothing left to clean up

        size = destination.stat().st_size
        print("[DOWNLOAD] Saved:", destination, size, flush=True)
        return {
            "success": True,
            "cancelled": False,
            "filename": destination.name,
            "file_path": str(destination),
            "size": size,
        }

    except urllib.error.HTTPError as error:
        return {"success": False, "error": f"Download failed. HTTP status: {error.code}"}
    except Exception as error:
        print("[DOWNLOAD ERROR]", error, flush=True)
        return {"success": False, "error": str(error)}
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def run_server():
    serve(flask_app, host=HOST, port=PORT, threads=16)


def server_is_up():
    try:
        urllib.request.urlopen(f"http://{local_host()}:{PORT}/health", timeout=1)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def wait_until_ready(timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server_is_up():
            return
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JTViewer.Desktop")
    except Exception:
        pass

    if not server_is_up():
        threading.Thread(target=run_server, daemon=True).start()
        wait_until_ready()

    window = webview.create_window("JT Viewer", APP_URL, width=1280, height=800)
    window.expose(download_file)
    webview.start(gui="edgechromium")