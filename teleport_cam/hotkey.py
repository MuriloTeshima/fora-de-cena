from __future__ import annotations
from threading import Event,Thread
import ctypes
import sys

class RestoreHotkey:
    """Optional Win32 shortcut; other desktops keep the window shortcut and button."""
    def __init__(self) -> None:
        self.requested=Event()
        self.stop=Event()
        self.registered=False
        self.ready=Event()
        self.thread: Thread | None = None
        if sys.platform == 'win32':
            self.thread=Thread(target=self._listen,daemon=True,name='restore-hotkey')
            self.thread.start()
        else:
            self.ready.set()

    def _listen(self) -> None:
        try:
            self._listen_windows()
        except (OSError, AttributeError):
            self.registered = False
        finally:
            self.ready.set()

    def _listen_windows(self) -> None:
        from ctypes import wintypes
        user32=ctypes.WinDLL('user32',use_last_error=True)
        user32.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
        user32.RegisterHotKey.restype=wintypes.BOOL
        user32.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
        user32.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
        self.registered=bool(user32.RegisterHotKey(None,0x4A31,0x4000,0x77)) # MOD_NOREPEAT, F8
        self.ready.set()
        if not self.registered:
            return
        try:
            message=wintypes.MSG()
            while not self.stop.wait(0.04):
                while user32.PeekMessageW(ctypes.byref(message),None,0x0312,0x0312,1):
                    self.requested.set()
        finally:
            user32.UnregisterHotKey(None,0x4A31)
            self.registered=False

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=0.5)
