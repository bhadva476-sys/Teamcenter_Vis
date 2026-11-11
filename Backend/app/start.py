"""Start the Flask application with Waitress in the current desktop session."""

import sys
from pathlib import Path
import os
import time
import ctypes

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from waitress import serve

from app import create_app
from app.config import HOST, PORT
from app.services.database import DatabaseStartupError, verify_database_connection

# 1. ADD THIS FUNCTION TO POP THE APPLICATION TO THE FRONT
# def bring_to_front():
#     try:
#         # Give the server a split second to spin up completely
#         time.sleep(1.0)
        
#         # Automatically launch the web dashboard link in the default browser
#         os.system(f"start http://{HOST}:{PORT}/")
        
#         # Optional: Use pywinauto to find your browser/app window and snap it over Teamcenter Visualization
#         from pywinauto import Application
#         app_win = Application(backend="win32").connect(title_re=".*JT Studio.*")
#         app_win.top_window().set_focus()
#         print("--> App window successfully brought to foreground.", flush=True)
#     except Exception as e:
#         # Fails silently if browser focus tracking is blocked by Windows permissions
#         pass

def bring_to_front():
    try:
        # Give the server a moment to fully initialize
        time.sleep(1.0)
        
        # Open your web dashboard in the default browser
        os.system(f"start http://{HOST}:{PORT}/")
        time.sleep(1.5)  # Wait for the browser window to open and render

        # Define Windows API functions safely with proper data types
        User32 = ctypes.windll.user32
        
        # Callback prototype: BOOL EnumWindowsProc(HWND hwnd, LPARAM lParam)
        # Note: wintypes.LPARAM is basically a pointer/long integer size type
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def foreach_window(hwnd, lParam):
            if User32.IsWindowVisible(hwnd):
                length = User32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    User32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    
                    # Match your web tab title keyword
                    if "JT" in title or "Files" in title:
                        User32.ShowWindow(hwnd, 9)  # 9 = SW_RESTORE
                        User32.SetForegroundWindow(hwnd)
                        print(f"--> [SUCCESS] Brought web view to front: {title}", flush=True)
                        return False  # Stop searching (breaks the loop)
            return True

        # Execute window scan loop
        cb = EnumWindowsProc(foreach_window)
        User32.EnumWindows(cb, 0)

    except Exception as e:
        print(f"Window bring_to_front error: {e}", flush=True)


if __name__ == "__main__":
    app = create_app()
    print("Checking MySQL connection...", flush=True)
    try:
        verify_database_connection(app.config)
    except DatabaseStartupError as error:
        raise SystemExit(
            f"JT Studio was not started because the database is unavailable. {error}"
        ) from error

    print("MySQL connection successful.", flush=True)
    print(f"Starting JT converter at http://{HOST}:{PORT}", flush=True)
    
    # 2. TRIGGER THE WINDOW MANAGEMENT FOCUS LOOP IN A BACKGROUND THREAD
    import threading
    threading.Thread(target=bring_to_front, daemon=True).start()

    try:
        serve(app, host=HOST, port=PORT, threads=4)
    except OSError as error:
        raise SystemExit(
            f"Could not start the JT converter at {HOST}:{PORT}: {error}. "
            "Check whether another server is already using this address."
        ) from error

ctrl+shift+i