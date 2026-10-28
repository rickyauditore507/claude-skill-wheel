# Security

## Reporting

Open a private security advisory on GitHub, or email the maintainer. Please do not
file a public issue for exploitable problems.

## Scope and design notes

- The overlay listens to global keyboard/mouse hooks while running. It only reads
  the configured trigger; it does not log keystrokes.
- The VS Code extension opens an HTTP server bound to `127.0.0.1` on a random port.
  It only accepts `POST /focus-claude`, which focuses the Claude input.
- Imported community skills are third-party content. They are never executed by
  the wheel; importing copies `SKILL.md` into `~/.claude/skills/` after an explicit
  confirmation that shows the source repository and license.
- The catalog indexes public GitHub repositories only. Do not add private repos or
  personal profile data.
