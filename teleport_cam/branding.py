"""Desktop application identity and icons; no system-wide settings are changed."""
import os
import tkinter as tk
from .paths import resource_root

ICON=resource_root()/'assets'/'brand'/'app-icon.ico'


def set_process_identity() -> None:
    if os.name=='nt':
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ForaDeCena.Desktop')
        except (OSError,AttributeError):
            pass


def set_window_icon(window:tk.Tk | tk.Toplevel) -> None:
    if os.name == 'nt' and ICON.is_file():
        try:
            # CustomTkinter sees this explicit call and retains our icon after its startup timer.
            window.iconbitmap(default=str(ICON))
        except (tk.TclError,OSError):
            pass
    else:
        png = resource_root() / 'assets' / 'brand' / 'app-icon.png'
        try:
            image = tk.PhotoImage(master=window, file=str(png))
            window.iconphoto(True, image)
        except (tk.TclError, OSError):
            pass
