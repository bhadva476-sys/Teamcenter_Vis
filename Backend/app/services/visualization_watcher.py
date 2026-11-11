
import os
import threading
import time
from pathlib import Path

from pywinauto import Desktop

INSERT_SHORTCUT = "^+i"
FILE_DIALOG_TITLES = {"open", "open file", "insert", "insert file"}
VISUALIZATION_AUTOMATION_LOCK = threading.Lock()

VIS_EXE = Path(
    r"C:\Soft\Siemens\Visualization_mockup\Products\Mockup\VisView.exe"
)


def find_visualization_window():
    try:
        windows = []
        for window in Desktop(backend="uia").windows():
            title = window.window_text().strip()

            if title and (
                "visualization" in title.lower()
                or "mockup" in title.lower()
            ):
                windows.append((window, title))

        for window, _ in windows:
            try:
                if window.is_active():
                    return window
            except Exception:
                continue

        for window, title in windows:
            if ".jt" in title.casefold():
                return window

        if windows:
            return windows[0][0]
    except Exception as error:
        print("Window detection error:", error)

    return None


def active_popup(main_window):
    """Return the active modal popup handle, process ID, and title."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    handle = user32.GetWindow(main_window.handle, 6)  # GW_ENABLEDPOPUP
    if not handle or handle == main_window.handle:
        return None

    user32.GetWindowTextW.argtypes = (
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    )
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    title = ctypes.create_unicode_buffer(512)
    process_id = wintypes.DWORD()
    user32.GetWindowTextW(handle, title, len(title))
    user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
    return handle, process_id.value, title.value


def _activate_window(hwnd):
    """Activate a top-level window even when Windows blocks direct focus changes."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = (
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.BOOL,
    )
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.SetFocus.argtypes = (wintypes.HWND,)
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    target = wintypes.HWND(hwnd)
    foreground = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    target_thread = user32.GetWindowThreadProcessId(target, None)
    current_thread = kernel32.GetCurrentThreadId()
    attached = []

    for thread_id in {foreground_thread, target_thread}:
        if thread_id and thread_id != current_thread:
            if user32.AttachThreadInput(current_thread, thread_id, True):
                attached.append(thread_id)

    try:
        user32.ShowWindow(target, 9)
        user32.BringWindowToTop(target)
        user32.SetForegroundWindow(target)
        user32.SetFocus(target)
        return user32.GetForegroundWindow() == target
    finally:
        for thread_id in reversed(attached):
            user32.AttachThreadInput(current_thread, thread_id, False)


def _select_ribbon_tab(window_spec, tab_name):
    matching_tabs = []
    for tab in window_spec.descendants(control_type="TabItem"):
        try:
            if (
                tab.window_text().strip().casefold() == tab_name.casefold()
                and tab.rectangle().top < 100
            ):
                matching_tabs.append(tab)
        except Exception:
            continue

    if not matching_tabs:
        return False

    tab = min(matching_tabs, key=lambda candidate: candidate.rectangle().top)
    try:
        tab.select()
    except Exception:
        tab.click_input()
    return True


def _wait_for_open_dialog(main_window, timeout=15):
    """Wait for Teamcenter Visualization's native Open file dialog."""
    deadline = time.monotonic() + timeout
    desktop = Desktop(backend="win32")

    while time.monotonic() < deadline:
        for dialog_window in desktop.windows():
            try:
                if (
                    dialog_window.handle == main_window.handle
                    or not dialog_window.is_visible()
                    or dialog_window.element_info.class_name != "#32770"
                    or dialog_window.window_text().strip().casefold() != "open"
                ):
                    continue

                dialog = desktop.window(handle=dialog_window.handle)
                filename = dialog.child_window(control_id=3078)
                open_button = dialog.child_window(control_id=1)
                if filename.exists(timeout=0.1) and open_button.exists(timeout=0.1):
                    return dialog, filename, open_button
            except Exception:
                continue
        time.sleep(0.2)

    raise TimeoutError(
        "Teamcenter Visualization's native Open file dialog did not appear."
    )


def _trigger_open_dialog(window, native_window):
    """Open Visualization's file picker through its ribbon Open command."""
    native_window.restore()
    _activate_window(native_window.handle)

    window_spec = Desktop(backend="uia").window(handle=window.handle)
    _select_ribbon_tab(window_spec, "Assembly")
    open_command = window_spec.child_window(
        title="Open",
        control_type="Button",
    )
    try:
        ribbon_open_exists = open_command.exists(timeout=2)
    except Exception:
        ribbon_open_exists = False

    if ribbon_open_exists:
        try:
            open_command.invoke()
        except Exception:
            try:
                open_command.click_input()
            except Exception:
                ribbon_open_exists = False
        if ribbon_open_exists:
            return _wait_for_open_dialog(native_window)

    native_window.type_keys("^o")
    try:
        return _wait_for_open_dialog(native_window, timeout=5)
    except TimeoutError:
        try:
            application_menu = window_spec.child_window(
                title="Application menu",
                control_type="Button",
            )
            application_menu.invoke()
            open_command = window_spec.child_window(
                title_re=r"Open\.\.\..*",
                control_type="MenuItem",
            )
            open_command.wait("visible", timeout=3)
            open_command.invoke()
        except Exception as error:
            raise TimeoutError(
                "Could not open Teamcenter Visualization's File > Open dialog "
                "using the ribbon, Ctrl+O, or the application menu."
            ) from error
        return _wait_for_open_dialog(native_window)


def _wait_for_insert_dialog(main_window, timeout=15):
    """Wait for Teamcenter Visualization's native Insert file dialog."""
    deadline = time.monotonic() + timeout
    desktop = Desktop(backend="win32")

    while time.monotonic() < deadline:
        for dialog_window in desktop.windows():
            try:
                if (
                    dialog_window.handle == main_window.handle
                    or not dialog_window.is_visible()
                    or dialog_window.element_info.class_name != "#32770"
                    or dialog_window.window_text().strip().casefold()
                    not in FILE_DIALOG_TITLES
                ):
                    continue

                dialog = desktop.window(handle=dialog_window.handle)
                filename = dialog.child_window(control_id=3078)
                insert_button = dialog.child_window(control_id=1)
                if filename.exists(timeout=0.1) and insert_button.exists(
                    timeout=0.1
                ):
                    return dialog, filename, insert_button
            except Exception:
                continue
        time.sleep(0.2)

    raise TimeoutError(
        "Teamcenter Visualization's native Insert file dialog did not appear."
    )


def _trigger_insert_dialog(window, native_window):
    """Open Visualization's Insert dialog to add a JT to the current model."""
    native_window.restore()
    _activate_window(native_window.handle)
    native_window.type_keys(INSERT_SHORTCUT)

    try:
        return _wait_for_insert_dialog(native_window)
    except TimeoutError:
        window_spec = Desktop(backend="uia").window(handle=window.handle)
        try:
            application_menu = window_spec.child_window(
                title="Application menu",
                control_type="Button",
            )
            application_menu.invoke()
            insert_command = window_spec.child_window(
                title_re=r"Insert.*",
                control_type="MenuItem",
                found_index=0,
            )
            insert_command.wait("visible", timeout=3)
            insert_command.invoke()
        except Exception as error:
            raise TimeoutError(
                "Could not open Teamcenter Visualization's Insert dialog "
                "using Ctrl+Shift+I or the application menu."
            ) from error
        return _wait_for_insert_dialog(native_window)


def _has_open_jt_model(window):
    """Return whether the Visualization session already contains a JT model."""
    titles = [window.window_text().strip()]
    titles.extend(
        child.window_text().strip()
        for child in window.descendants(control_type="Window")
    )
    titles.extend(
        tab.window_text().strip()
        for tab in window.descendants(control_type="TabItem")
    )
    return any(".jt" in title.casefold() for title in titles)


def _wait_for_list_item(list_view, name, timeout, starts_with=False):
    deadline = time.monotonic() + timeout
    expected_name = name.casefold()
    while time.monotonic() < deadline:
        for index in range(list_view.item_count()):
            item = list_view.get_item(index)
            item_name = item.text().strip().casefold()
            if item_name == expected_name or (
                starts_with and item_name.startswith(expected_name)
            ):
                return item
        time.sleep(0.2)
    visible_items = [
        list_view.get_item(index).text().strip()
        for index in range(list_view.item_count())
    ]
    raise TimeoutError(
        f"Teamcenter Visualization's file dialog did not show {name!r}. "
        f"Visible entries: {visible_items[:20]!r}"
    )


def _navigate_to_file(dialog, file_path, timeout=15):
    """Browse the legacy native picker using its folder-name edit control."""
    file_path = Path(file_path).resolve()
    if not file_path.drive:
        raise ValueError(f"JT file path must be absolute: {file_path}")

    list_view = dialog.child_window(control_id=1006)
    filename_edit = dialog.child_window(control_id=3078)
    open_button = dialog.child_window(control_id=1)

    for index in range(list_view.item_count()):
        item = list_view.get_item(index)
        if item.text().strip().casefold() == file_path.name.casefold():
            return item

    my_computer = dialog.child_window(control_id=3070)
    my_computer.click()
    filename_edit.set_edit_text(file_path.drive + "\\")
    open_button.click()

    folder_parts = file_path.parent.parts[1:]
    for folder_name in folder_parts:
        _wait_for_list_item(list_view, folder_name, timeout)
        filename_edit.set_edit_text(folder_name + "\\")
        open_button.click()

    return _wait_for_list_item(list_view, file_path.name, timeout)


def _navigate_and_submit_file(
    dialog,
    submit_button,
    file_path,
    timeout=15,
):
    """Browse to the exact JT file and submit it in the native picker."""
    file_item = _navigate_to_file(dialog, file_path, timeout)
    file_item.click_input()
    submit_button.wait("enabled", timeout=2)
    submit_button.click()
    dialog.wait_not("visible", timeout=15)


def open_file_in_visualization(file_path, open_in_new_document=False):
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"JT file not found: {file_path}")

    if not VIS_EXE.exists():
        raise FileNotFoundError(f"Application not found: {VIS_EXE}")

    with VISUALIZATION_AUTOMATION_LOCK:
        window = find_visualization_window()
        if window is None:
            try:
                os.startfile(str(VIS_EXE))
            except OSError as error:
                raise RuntimeError(
                    f"Windows could not start Teamcenter Visualization: {error}"
                ) from error
            deadline = time.monotonic() + 90
            while window is None and time.monotonic() < deadline:
                time.sleep(0.5)
                window = find_visualization_window()
        if window is None:
            raise TimeoutError(
                "Teamcenter Visualization did not open within 90 seconds."
            )

        native_window = Desktop(backend="win32").window(handle=window.handle)
        if not open_in_new_document and _has_open_jt_model(window):
            dialog, filename, submit_button = _trigger_insert_dialog(
                window,
                native_window,
            )
        else:
            dialog, filename, submit_button = _trigger_open_dialog(
                window,
                native_window,
            )
        _navigate_and_submit_file(
            dialog,
            submit_button,
            file_path,
        )

    print("JT file loaded in Teamcenter Visualization:", file_path)
    return True
