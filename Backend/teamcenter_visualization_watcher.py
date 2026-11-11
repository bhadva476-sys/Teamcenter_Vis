import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.services import visualization_watcher

# Single-instance guard: a second watcher exits immediately
_lock = socket.socket()
try:
    _lock.bind(("127.0.0.1", 50998))
except OSError:
    print("Watcher already running.")
    sys.exit(0)

BUSY_FLAG = Path(tempfile.gettempdir()) / "teamcenter_visualization_busy.flag"
APP_TITLE = "JT Viewer"
INSERT_TITLES = {"insert file", "insert"}   # "open" removed: your Add flow no longer uses it
CLOSE_VISUALIZATION_DIALOG = True


def find_viewer_window():
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows():
        try:
            if w.window_text().strip() == APP_TITLE:
                return w
        except Exception:
            continue
    return None


# def force_foreground(hwnd):
#     import ctypes
#     from ctypes import wintypes

#     user32 = ctypes.WinDLL("user32", use_last_error=True)
#     kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
#     user32.GetForegroundWindow.restype = wintypes.HWND
#     user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
#     user32.GetWindowThreadProcessId.restype = wintypes.DWORD
#     user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
#     user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
#     user32.SetWindowPos.argtypes = (
#         wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
#         ctypes.c_int, ctypes.c_int, wintypes.UINT,
#     )
#     user32.BringWindowToTop.argtypes = (wintypes.HWND,)
#     user32.SetForegroundWindow.argtypes = (wintypes.HWND,)

#     hwnd = wintypes.HWND(hwnd)
#     user32.ShowWindow(hwnd, 9)  # SW_RESTORE

#     foreground = user32.GetForegroundWindow()
#     fg_tid = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
#     my_tid = kernel32.GetCurrentThreadId()
#     attached = bool(fg_tid and fg_tid != my_tid and user32.AttachThreadInput(my_tid, fg_tid, True))
#     try:
#         flags = 0x0001 | 0x0002  # SWP_NOSIZE | SWP_NOMOVE
#         user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, flags)  # topmost
#         user32.SetWindowPos(hwnd, wintypes.HWND(-2), 0, 0, 0, 0, flags)  # normal again
#         user32.BringWindowToTop(hwnd)
#         user32.SetForegroundWindow(hwnd)
#     finally:
#         if attached:
#             user32.AttachThreadInput(my_tid, fg_tid, False)

def force_foreground(hwnd):
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetForegroundWindow.restype = wintypes.HWND

    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    user32.AttachThreadInput.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.BOOL,
    ]
    user32.AttachThreadInput.restype = wintypes.BOOL

    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]

    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    hwnd = wintypes.HWND(hwnd)
    user32.ShowWindow(hwnd, 9)

    foreground = user32.GetForegroundWindow()
    foreground_pid = wintypes.DWORD()

    fg_tid = (
        user32.GetWindowThreadProcessId(
            foreground, ctypes.byref(foreground_pid)
        )
        if foreground
        else 0
    )
    my_tid = kernel32.GetCurrentThreadId()

    attached = False

    if fg_tid and fg_tid != my_tid:
        attached = bool(
            user32.AttachThreadInput(my_tid, fg_tid, True)
        )

    try:
        flags = 0x0001 | 0x0002
        user32.SetWindowPos(
            hwnd, wintypes.HWND(-1), 0, 0, 0, 0, flags
        )
        user32.SetWindowPos(
            hwnd, wintypes.HWND(-2), 0, 0, 0, 0, flags
        )
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(my_tid, fg_tid, False)

APP_EXE = Path(r"C:\Project\new\Backend\dist\JTViewer\JTViewer.exe")

def launch_or_focus():
    win = find_viewer_window()
    if win is None:
        print("Launching JT Viewer...")
        log = open(r"C:\Project\new\Backend\desktop_app.log", "ab")
        subprocess.Popen(
            [str(APP_EXE)],
            cwd=str(APP_EXE.parent),
            stdout=log,
            stderr=log,
        )
        deadline = time.monotonic() + 20
        while win is None and time.monotonic() < deadline:
            time.sleep(0.3)
            win = find_viewer_window()
    if win is not None:
        try:
            force_foreground(win.handle)
        except Exception as error:
            print("Could not bring the app to the front:", error)


def _popup_gone(handle):
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    h = wintypes.HWND(handle)
    for _ in range(10):
        if not user32.IsWindow(h) or not user32.IsWindowVisible(h):
            return True
        time.sleep(0.1)
    return False


def close_popup(handle):
    import ctypes
    from ctypes import wintypes
    from pywinauto import Desktop

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    hwnd = wintypes.HWND(handle)

    # 1. Click "Cancel" found by its text
    try:
        dlg = Desktop(backend="uia").window(handle=handle)
        btn = dlg.child_window(title="Cancel", control_type="Button")
        if btn.exists(timeout=1):
            try:
                btn.invoke()
            except Exception:
                btn.click_input()
            if _popup_gone(handle):
                print("Insert File dialog closed (Cancel button).")
                return
    except Exception as error:
        print("Cancel button method failed:", error)

    # 2. SC_CLOSE, 3. WM_CLOSE
    user32.PostMessageW(hwnd, 0x0112, 0xF060, 0)
    if _popup_gone(handle):
        print("Insert File dialog closed (SC_CLOSE).")
        return
    user32.PostMessageW(hwnd, 0x0010, 0, 0)
    if _popup_gone(handle):
        print("Insert File dialog closed (WM_CLOSE).")
        return
    print("Could not close the Insert File dialog.")


def watch(interval=0.5):
    print("Watching Teamcenter Visualization... (Ctrl+C to stop)")
    last_handle = None
    while True:
        try:
            window = visualization_watcher.find_visualization_window()
            popup = visualization_watcher.active_popup(window) if window else None
            handle = popup[0] if popup else None
            if popup and handle != last_handle:
                title = popup[2].strip().lower()
                if title and title != "project workspace":
                    print(f"Teamcenter Visualization dialog appeared: {popup[2]!r}")
                if title in INSERT_TITLES and not BUSY_FLAG.exists():
                    print("Insert detected, opening JT Viewer...")
                    last_handle = handle
                    try:
                        launch_or_focus()
                    except Exception as error:
                        print("launch failed:", error)
                    if CLOSE_VISUALIZATION_DIALOG:
                        try:
                            close_popup(handle)
                        except Exception as error:
                            print("close failed:", error)
                    try:
                        w = find_viewer_window()
                        if w is not None:
                            force_foreground(w.handle)
                    except Exception as error:
                        print("focus failed:", error)
                    continue
            last_handle = handle
        except Exception as error:
            print("watcher:", error)
        time.sleep(interval)


if __name__ == "__main__":
    watch()