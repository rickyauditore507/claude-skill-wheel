"""Windows input helpers: synthetic typing, key state polling, window flags."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_CAPITAL = 0x14
VK_LWIN = 0x5B
VK_RWIN = 0x5C


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short


def _key_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _send(*items: INPUT) -> None:
    arr = (INPUT * len(items))(*items)
    user32.SendInput(len(items), arr, ctypes.sizeof(INPUT))


def key_down(vk: int) -> None:
    _send(_key_input(vk=vk))


def key_up(vk: int) -> None:
    _send(_key_input(vk=vk, flags=KEYEVENTF_KEYUP))


def tap(vk: int) -> None:
    _send(_key_input(vk=vk), _key_input(vk=vk, flags=KEYEVENTF_KEYUP))


def release_modifiers() -> None:
    for vk in (VK_MENU, VK_CONTROL, VK_SHIFT, VK_LWIN, VK_RWIN):
        key_up(vk)


CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32.OpenClipboard.argtypes = (wintypes.HWND,)
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = (wintypes.UINT,)
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
user32.SetClipboardData.restype = wintypes.HANDLE
kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = (wintypes.HANDLE,)
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = (wintypes.HANDLE,)
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = (wintypes.HANDLE,)
kernel32.GlobalFree.restype = wintypes.HANDLE


def _open_clipboard() -> bool:
    for _ in range(8):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def get_clipboard_text() -> str | None:
    if not _open_clipboard():
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        except Exception:
            return None
        finally:
            kernel32.GlobalUnlock(handle)
    except Exception:
        return None
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text: str) -> bool:
    if not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return False
        try:
            ctypes.memmove(ptr, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def send_focus_claude() -> None:
    """Focus the Claude input in the ACTIVE VS Code window.

    The extension contributes ctrl+alt+shift+f12 to claude-vscode.focus.
    Sending the chord (instead of calling a bridge in one window) is what makes
    multi-window / dragged-out Claude panels behave correctly.
    """
    VK_F12 = 0x7B
    _send(_key_input(vk=VK_CONTROL), _key_input(vk=VK_MENU), _key_input(vk=VK_SHIFT),
          _key_input(vk=VK_F12),
          _key_input(vk=VK_F12, flags=KEYEVENTF_KEYUP),
          _key_input(vk=VK_SHIFT, flags=KEYEVENTF_KEYUP),
          _key_input(vk=VK_MENU, flags=KEYEVENTF_KEYUP),
          _key_input(vk=VK_CONTROL, flags=KEYEVENTF_KEYUP))


def send_paste() -> None:
    """Ctrl+V into whatever has focus (webview textareas, native edits)."""
    VK_V = 0x56
    _send(_key_input(vk=VK_CONTROL),
          _key_input(vk=VK_V),
          _key_input(vk=VK_V, flags=KEYEVENTF_KEYUP),
          _key_input(vk=VK_CONTROL, flags=KEYEVENTF_KEYUP))


def send_ctrl_esc() -> None:
    _send(_key_input(vk=VK_CONTROL),
          _key_input(vk=VK_ESCAPE),
          _key_input(vk=VK_ESCAPE, flags=KEYEVENTF_KEYUP),
          _key_input(vk=VK_CONTROL, flags=KEYEVENTF_KEYUP))


def type_text(text: str, inter_char_delay: float = 0.002) -> None:
    """Type as Unicode, independent of the active keyboard layout."""
    for ch in text:
        if ch in ("\r", "\n"):
            tap(VK_RETURN)
        else:
            # UTF-16 code units: astral chars arrive as a surrogate pair
            data = ch.encode("utf-16-le")
            for i in range(0, len(data), 2):
                unit = int.from_bytes(data[i:i + 2], "little")
                _send(_key_input(scan=unit, flags=KEYEVENTF_UNICODE),
                      _key_input(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        if inter_char_delay:
            time.sleep(inter_char_delay)


def get_foreground_hwnd() -> int:
    return int(user32.GetForegroundWindow())


def set_foreground(hwnd: int) -> bool:
    if not hwnd:
        return False
    try:
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


def foreground_title() -> str:
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    return f"{cls.value} | {buf.value}"


def get_cursor_physical() -> tuple[int, int]:
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def is_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def press_esc() -> None:
    tap(VK_ESCAPE)


# ---- single instance / parent watch -------------------------------------

def create_single_instance(name: str) -> int | None:
    """Return a mutex handle, or None when another instance holds it."""
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return None
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return handle


def process_alive(pid: int) -> bool:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32.OpenProcess.restype = wintypes.HANDLE
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(h)


def apply_overlay_window_style(hwnd: int) -> None:
    """No-activate + tool window + topmost, so the wheel never steals focus."""
    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_LAYERED = 0x00080000
    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010

    user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    ex |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
