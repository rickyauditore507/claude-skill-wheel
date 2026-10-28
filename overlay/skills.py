"""Discover installed Claude Code skills from disk."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from config import load_usage
from pathlib import Path

HOME = Path.home()
PERSONAL_SKILLS = HOME / ".claude" / "skills"
PLUGINS_DIR = HOME / ".claude" / "plugins"
CLAUDE_JSON = HOME / ".claude.json"


@dataclass
class Skill:
    name: str
    command: str          # text inserted into the Claude prompt, without leading "/"
    description: str
    path: str
    source: str           # personal | project | plugin
    plugin: str = ""
    usage: int = 0
    detail: dict = field(default_factory=dict)


def _strip_quotes(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def parse_frontmatter(text: str) -> dict[str, str]:
    """Tolerant YAML-frontmatter reader for the fields skills actually use."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].splitlines()
    out: dict[str, str] = {}
    key = None
    buf: list[str] = []
    folded = False

    def flush() -> None:
        nonlocal key, buf, folded
        if key is not None:
            val = " ".join(x.strip() for x in buf).strip() if folded else "\n".join(buf).strip()
            if val:
                out[key] = val
        key, buf, folded = None, [], False

    for raw in block:
        line = raw.rstrip()
        if not line.strip():
            if key is not None:
                buf.append("")
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            flush()
            key = m.group(1)
            val = m.group(2).strip()
            if val in (">", "|", ">-", "|-"):
                folded = True
                buf = []
            elif val:
                out[key] = _strip_quotes(val)
                key = None
        elif key is not None:
            buf.append(line)
    flush()
    return out


def _read_skill(path: Path) -> tuple[str, str] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    meta = parse_frontmatter(text)
    name = (meta.get("name") or path.parent.name).strip()
    desc = meta.get("description", "").strip()
    desc = re.sub(r"\s+", " ", desc)
    return name, desc


def _plugin_name_for(skill_md: Path) -> str:
    """Nearest plugin.json above a skills/<x>/SKILL.md, else the plugin folder."""
    p = skill_md.parent.parent  # skills/
    cur = p.parent
    for _ in range(4):
        manifest = cur / ".claude-plugin" / "plugin.json"
        if manifest.exists():
            try:
                return json.loads(manifest.read_text(encoding="utf-8")).get("name") or cur.name
            except Exception:
                return cur.name
        if (cur / "plugin.json").exists():
            return cur.name
        if cur == cur.parent:
            break
        cur = cur.parent
    return skill_md.parent.parent.parent.name if skill_md.parent.parent.parent else "plugin"


def _scan_root(root: Path, source: str, plugin: str = "") -> list[Skill]:
    out: list[Skill] = []
    if not root.exists():
        return out
    try:
        entries = list(root.iterdir())
    except Exception:
        return out
    for d in entries:
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if not md.exists():
            continue
        parsed = _read_skill(md)
        if not parsed:
            continue
        name, desc = parsed
        cmd = f"{plugin}:{name}" if plugin else name
        out.append(Skill(name=name, command=cmd, description=desc,
                         path=str(md), source=source, plugin=plugin))
    return out


def _scan_plugins() -> list[Skill]:
    out: list[Skill] = []
    if not PLUGINS_DIR.exists():
        return out
    seen: set[str] = set()
    for md in PLUGINS_DIR.rglob("SKILL.md"):
        # only skills that sit in a "skills" directory, and skip caches
        if md.parent.parent.name != "skills":
            continue
        if "node_modules" in md.parts:
            continue
        plugin = _plugin_name_for(md)
        parsed = _read_skill(md)
        if not parsed:
            continue
        name, desc = parsed
        key = f"{plugin}:{name}"
        if key in seen:
            continue
        seen.add(key)
        out.append(Skill(name=name, command=key, description=desc,
                         path=str(md), source="plugin", plugin=plugin))
    return out


def external_usage() -> dict[str, int]:
    """Claude Code's own per-skill usage counters, when present."""
    try:
        data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
        usage = data.get("skillUsage") or {}
        return {str(k): int(v.get("usageCount", 0)) for k, v in usage.items() if isinstance(v, dict)}
    except Exception:
        return {}


def discover(config: dict, workspace: str | None = None) -> list[Skill]:
    sources = config.get("sources") or {}
    skills: list[Skill] = []
    if sources.get("personal", True):
        skills += _scan_root(PERSONAL_SKILLS, "personal")
    if sources.get("project", True) and workspace:
        for base in (Path(workspace) / ".claude" / "skills",):
            skills += _scan_root(base, "project")
    if sources.get("plugins", False):
        skills += _scan_plugins()

    # de-duplicate by command, personal wins
    by_cmd: dict[str, Skill] = {}
    order = {"personal": 0, "project": 1, "plugin": 2}
    for s in sorted(skills, key=lambda s: order.get(s.source, 9)):
        by_cmd.setdefault(s.command, s)

    used = external_usage()
    mine = load_usage()
    for s in by_cmd.values():
        s.usage = int(used.get(s.name, 0)) + int(mine.get(s.command, mine.get(s.name, 0)))

    exclude = {str(x).lower() for x in (config.get("exclude") or [])}
    pins = [str(x) for x in (config.get("pins") or [])]
    pin_index = {name: i for i, name in enumerate(pins)}

    items = [s for s in by_cmd.values() if s.name.lower() not in exclude
             and s.command.lower() not in exclude]

    def sort_key(s: Skill):
        if s.name in pin_index:
            return (0, pin_index[s.name], 0, s.name.lower())
        mode = config.get("sort", "usage")
        if mode == "name":
            return (1, 0, 0, s.name.lower())
        return (1, 0, -s.usage, s.name.lower())

    items.sort(key=sort_key)
    return items
