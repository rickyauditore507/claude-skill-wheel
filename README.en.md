# Skill Wheel

![Skill Wheel](assets/banner.png)

Hold **Ctrl + Alt + Space**, slide the mouse to a skill on the ring, scroll to
flip pages, and release to insert `/skill-name` into the Claude Code input.
Release without moving to cancel.

A transparent, always-on-top radial menu for Claude Code on Windows, plus a
VS Code companion extension that starts/stops it and focuses the Claude input.

## Install (from source)

```powershell
git clone https://github.com/rickyauditore507/claude-skill-wheel.git
cd claude-skill-wheel
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
powershell -File .\install.ps1
```

Reload the VS Code window. A **Skill Wheel** status-bar item appears; the
overlay starts automatically.

- Config / logs: `~/.claude/skill-wheel/`
- Skills are read from `~/.claude/skills/*/SKILL.md`

## How it works

| Part | Role |
| --- | --- |
| `overlay/` (Python + PySide6) | Transparent overlay, global hotkey, hover/scroll, insertion |
| `extension/` (VS Code) | Lifecycle, status bar, local `/focus-claude` bridge |

VS Code's extension API cannot draw transparent floating windows, so the ring is
a separate Python overlay; the extension only supervises it.

## Demo video

- Douyin: [Claude Code skill wheel](https://v.douyin.com/TC4KSCrMKCE/)
- Xiaohongshu: [Claude Code skill wheel](https://xhslink.cn/o/87189MkaioG)

## Notes

- **Do not use a bare Alt modifier** for the trigger: VS Code enters its menu
  access-key mode on Alt-down and a low-level hook cannot undo that. The default
  `Ctrl+Alt+Space` avoids it.
- While the ring is open, wheel events are suppressed system-wide so the page
  underneath does not scroll.
- The selected command is pasted from the clipboard; the previous clipboard text
  is restored shortly after.
- The VS Code bridge listens on `127.0.0.1` only.

## Development

```bash
python overlay/main.py --list
python overlay/main.py --demo --hover 2 --shot demo.png
python assets/make_poster.py
```

## License

Apache-2.0. PySide6/Qt and pynput are LGPL-3.0; see `THIRD_PARTY_NOTICES.md`.
