# Changelog

## 0.1.2 — 2026-10-30

- Fix: focus the Claude input in the **active** VS Code window. Dragged-out Claude
  panels now receive the command instead of the original window.
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
