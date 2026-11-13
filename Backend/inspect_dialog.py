from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="Insert File")
dlg.print_control_identifiers()