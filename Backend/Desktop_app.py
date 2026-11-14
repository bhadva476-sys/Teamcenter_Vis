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


class DesktopApi:
    def __init__(self):
        self.window = None

    
def download_file(self, file_id, filename):
    print("download_file called:", file_id, filename, flush=True)

    try:
        file_id = int(file_id)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid JT file ID.") from error

    if file_id < 1:
        raise ValueError("Invalid JT file ID.")

    filename = secure_filename(
        Path(str(filename).replace("\\", "/")).name
    )

    if not filename or Path(filename).suffix.lower() != ".jt":
        raise ValueError("A valid JT filename is required.")

    # Direct Windows Downloads folder
    downloads_folder = Path(r"C:\Users\Ashwin\Downloads")
    downloads_folder.mkdir(parents=True, exist_ok=True)

    destination = downloads_folder / filename

    # Build Flask download API URL
    server_host = HOST

    if server_host in ("", "0.0.0.0", "::"):
        server_host = "127.0.0.1"
    elif ":" in server_host and not server_host.startswith("["):
        server_host = f"[{server_host}]"

    download_url = (
        f"http://{server_host}:{PORT}/api/jt-files/{file_id}/download"
    )

    temporary_path = None

    try:
        print("[DOWNLOAD] Requesting:", download_url, flush=True)

        with urllib.request.urlopen(download_url, timeout=60) as response:

            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=downloads_folder,
                prefix=f".{destination.name}.",
                suffix=".part",
                delete=False,
            ) as output:

                temporary_path = Path(output.name)
                shutil.copyfileobj(response, output)

        # Move completed download to final destination
        os.replace(temporary_path, destination)

        print("[DOWNLOAD] SUCCESS", flush=True)
        print("[DOWNLOAD] Saved:", destination, flush=True)
        print("[DOWNLOAD] Size:", destination.stat().st_size, flush=True)

        return {
            "success": True,
            "cancelled": False,
            "filename": destination.name,
            "file_path": str(destination),
            "size": destination.stat().st_size
        }

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Download failed. HTTP status: {error.code}"
        ) from error

    except Exception as error:
        print("[DOWNLOAD ERROR]", str(error), flush=True)
        raise

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def run_server():
    serve(flask_app, host=HOST, port=PORT)


def server_is_up():
    try:
        urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=1)
        return True
    except urllib.error.HTTPError:
        return True      # server chal raha hai, bas page ne error diya
    except Exception:
        return False     # server abhi start nahi hua


def wait_until_ready(timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server_is_up():
            return
        time.sleep(0.2)


if __name__ == "__main__":
    if not server_is_up():
        threading.Thread(target=run_server, daemon=True).start()
        wait_until_ready()
    desktop_api = DesktopApi()
    desktop_api.window = webview.create_window(
        "JT Viewer",
        f"http://{HOST}:{PORT}/",
        width=1280,
        height=800,
        js_api=desktop_api,
    )
    webview.start()
