# Changelog

## 0.1.2 — 2026-10-30

- Fix: stop moving the foreground window. `focusClaude` now defaults to `false`;
  the command is pasted into whatever input is focused (dragged-out Claude panels
  included). The opt-in focus chord is documented as best-effort.
- Remove the local HTTP focus bridge; focus is a contributed keybinding
  (`Ctrl+Alt+Shift+F12` -> `claude-vscode.focus`).

## 0.1.1 — 2026-10-28

- Fix: wheel events no longer scroll the page underneath while the wheel is open
  (true system-wide suppression via `suppress_event`).
- Fix: hover/movement updates are driven by the controller poll timer, so a
  missed overlay timer can no longer cause accidental cancellation.
- Fix: multi-monitor hit-testing uses window-local coordinates.
- Change: selected commands are pasted (clipboard is restored afterwards)
  instead of typed, avoiding a swallowed first character.
- Add: Apache-2.0 license, third-party notices, CI, community catalog schema.

## 0.1.0

- First working overlay + VS Code companion.
