# Skill Wheel (VS Code companion)

A radial skill picker for Claude Code. Hold **Ctrl + Alt + Space** (default; Alt-based triggers steal VS Code's menu), slide the mouse to a skill, scroll to flip the ring, and release to insert `/skill-name` into the Claude input.

This extension is the lifecycle companion: it starts/stops the Python overlay, shows a status-bar switch, and focuses the Claude input through a local-only bridge (`127.0.0.1`, random port).

## Requirements

- Windows 10/11
- Python 3.12 with `PySide6-Essentials` and `pynput`, or the bundled overlay executable
- Claude Code extension for VS Code

## Commands

- `Skill Wheel: Start overlay`
- `Skill Wheel: Stop overlay`
- `Skill Wheel: Restart overlay`
- `Skill Wheel: Open config`
- `Skill Wheel: Show logs`

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `skillWheel.autoStart` | `true` | Start the overlay when VS Code starts |
| `skillWheel.projectDir` | `~/skill-wheel` | Folder containing `overlay/main.py` |
| `skillWheel.pythonPath` | `<projectDir>/.venv/Scripts/pythonw.exe` | Interpreter with PySide6 |
| `skillWheel.showStatusBar` | `true` | Show the status-bar indicator |

## Privacy

The bridge listens on `127.0.0.1` only. No telemetry, no network calls. Skill metadata is read from local `SKILL.md` files.

Licensed under Apache-2.0.
