"""Windows application identity and icon; no changes to system-wide settings."""
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
    if ICON.is_file():
        try:
            # CustomTkinter sees this explicit call and retains our icon after its startup timer.
            window.iconbitmap(default=str(ICON))
        except (tk.TclError,OSError):
            pass
