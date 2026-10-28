"""Global hotkey + wheel listener (pynput), with combo suppression."""
from __future__ import annotations

import ctypes
from typing import Callable

from pynput import keyboard as pkb
from pynput import mouse as pms

from wininput import get_cursor_physical, is_down, VK_MENU, VK_CONTROL, VK_SHIFT, VK_LWIN, VK_RWIN

WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
WM_MOUSEWHEEL, WM_MOUSEHWHEEL = 0x020A, 0x020E

user32 = ctypes.WinDLL("user32", use_last_error=True)

MOD_ALIASES = {
    "alt": "alt", "option": "alt",
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "win": "win", "super": "win", "meta": "win", "cmd": "win",
}

NAMED_VKS = {
    "space": 0x20, "caps_lock": 0x14, "capslock": 0x14, "tab": 0x09,
    "enter": 0x0D, "return": 0x0D, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "page_up": 0x21, "page_down": 0x22,
    "backquote": 0xC0, "grave": 0xC0, "`": 0xC0,
}


def _char_vk(ch: str) -> int:
    if len(ch) == 1:
        vk = user32.VkKeyScanW(ord(ch)) & 0xFF
        if vk and vk != 0xFF:
            return vk
    return 0


def parse_trigger(trigger: str) -> tuple[set[str], str, int]:
    """'alt+`' -> ({'alt'}, '`', 0xC0). Raises ValueError on bad input."""
    parts = [p.strip() for p in str(trigger).lower().split("+") if p.strip()]
    if not parts:
        raise ValueError("empty trigger")
    mods: set[str] = set()
    key = None
    for p in parts:
        if p in MOD_ALIASES:
            mods.add(MOD_ALIASES[p])
        else:
            if key is not None:
                raise ValueError(f"trigger has two keys: {trigger}")
            key = p
    if key is None:
        raise ValueError("trigger needs a non-modifier key (e.g. alt+`)")
    vk = NAMED_VKS.get(key)
    if vk is None:
        vk = _char_vk(key)
    if not vk:
        # pynput may know special keys by name (f1..f24)
        try:
            k = getattr(pkb.Key, key)
            vk = getattr(k, "value", None).vk if hasattr(getattr(k, "value", None), "vk") else 0
        except Exception:
            vk = 0
    if not vk:
        raise ValueError(f"unknown trigger key: {key}")
    return mods, key, int(vk)


MOD_VKS = {
    "alt": {0x12, 0xA4, 0xA5},
    "ctrl": {0x11, 0xA2, 0xA3},
    "shift": {0x10, 0xA0, 0xA1},
    "win": {0x5B, 0x5C},
}


def _mod_vks(name: str) -> set[int]:
    return MOD_VKS.get(name, set())


def _mod_down(name: str) -> bool:
    if name == "alt":
        return is_down(VK_MENU)
    if name == "ctrl":
        return is_down(VK_CONTROL)
    if name == "shift":
        return is_down(VK_SHIFT)
    if name == "win":
        return is_down(VK_LWIN) or is_down(VK_RWIN)
    return False


class Hotkey:
    """Watches for one combo everywhere, swallowing its non-modifier key."""

    def __init__(self, trigger: str,
                 on_activate: Callable[[], None],
                 on_scroll: Callable[[int], None] | None = None,
                 suppress_scroll: Callable[[], bool] | None = None):
        self.trigger = trigger
        self.mods, self.key_name, self.key_vk = parse_trigger(trigger)
        self.on_activate = on_activate
        self.on_scroll = on_scroll
        self.suppress_scroll = suppress_scroll
        self._suppressing = False
        self._armed = True
        self._held = False
        self.activation_pos: tuple[int, int] | None = None
        self._kb: pkb.Listener | None = None
        self._mouse: pms.Listener | None = None

    # ---- requirement checks ----
    def held(self) -> bool:
        # The trigger key itself is suppressed system-wide, so polling
        # GetAsyncKeyState for it is unreliable. Track the combo from hook
        # events instead, and only poll the (unsuppressed) modifiers.
        if not self._held:
            return False
        return all(_mod_down(m) for m in self.mods)

    def mods_down(self) -> bool:
        return all(_mod_down(m) for m in self.mods)

    # ---- listeners ----
    def start(self) -> None:
        self._kb = pkb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            win32_event_filter=self._win32_filter,
            suppress=False,
        )
        self._kb.daemon = True
        self._kb.start()
        if self.on_scroll:
            self._mouse = pms.Listener(on_scroll=self._on_scroll,
                                       win32_event_filter=self._mouse_filter)
            self._mouse.daemon = True
            self._mouse.start()

    def stop(self) -> None:
        for listener in (self._kb, self._mouse):
            try:
                if listener:
                    listener.stop()
            except Exception:
                pass

    def _on_scroll(self, x, y, dx, dy) -> None:
        if self.on_scroll and dy:
            self.on_scroll(-1 if dy > 0 else 1)

    def _mouse_filter(self, msg: int, data) -> bool:
        """While the wheel is open, eat wheel events so the page underneath stays put."""
        if msg in (WM_MOUSEWHEEL, WM_MOUSEHWHEEL) and self.suppress_scroll:
            try:
                if not self.suppress_scroll():
                    return True
            except Exception:
                return True
            if msg == WM_MOUSEWHEEL and self.on_scroll:
                raw = int(getattr(data, "mouseData", 0)) & 0xFFFFFFFF
                delta = (raw >> 16) & 0xFFFF
                if delta >= 0x8000:
                    delta -= 0x10000
                if delta:
                    try:
                        self.on_scroll(-1 if delta > 0 else 1)
                    except Exception:
                        pass
            # Returning False only stops pynput's callback. Only suppress_event()
            # keeps the wheel from scrolling the page underneath.
            if self._mouse is not None:
                self._mouse.suppress_event()
            return False
        return True

    def _on_press(self, key) -> None:
        pass  # activation is decided in the win32 filter (needs suppression)

    def _on_release(self, key) -> None:
        pass

    def _win32_filter(self, msg: int, data) -> bool:
        try:
            vk = int(data.vkCode)
        except Exception:
            return True
        if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
            if vk == self.key_vk and self.mods_down():
                # Swallow the key AND its auto-repeats for as long as the combo is held.
                # Returning False alone only skips pynput's callback; suppress_event()
                # is what actually keeps the key away from the focused app.
                self._held = True
                if self._armed:
                    self._armed = False
                    self._suppressing = True
                    try:
                        self.activation_pos = get_cursor_physical()
                    except Exception:
                        self.activation_pos = None
                    try:
                        self.on_activate()
                    except Exception:
                        pass
                if self._kb is not None:
                    self._kb.suppress_event()   # raises SuppressException, consumed by the hook
                return False
        elif msg in (WM_KEYUP, WM_SYSKEYUP):
            if vk == self.key_vk:
                self._held = False
                self._armed = True
                if self._suppressing:
                    self._suppressing = False
                    if self._kb is not None:
                        self._kb.suppress_event()
                    return False
            if any(vk in _mod_vks(m) for m in self.mods):
                self._held = False
        return True
