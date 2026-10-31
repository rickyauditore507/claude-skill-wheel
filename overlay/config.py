"""Config + usage storage for Skill Wheel."""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

HOME = Path.home()
APP_VERSION = "0.2.0"
APP_DIR = HOME / ".claude" / "skill-wheel"
CONFIG_PATH = APP_DIR / "config.json"
USAGE_PATH = APP_DIR / "usage.json"

DEFAULT_CONFIG: dict = {
    "trigger": "ctrl+alt+space",
    "skillsPerPage": 8,
    "radius": 250,
    "innerRadius": 118,
    "sources": {"personal": True, "project": True, "plugins": False},
    "exclude": [],
    "pins": [],
    "sort": "usage",
    "insertMode": "insert",          # insert | insert_and_enter | clipboard
    "focusClaude": False,
    "trackUsage": True,
    "dimBackground": 0.38,
    "moveThreshold": 12,
    "theme": {
        "accent": "#D97757",
        "accentSoft": "#E8A487",
        "text": "#F3EEE8",
        "muted": "#9C948C",
        "panel": "#1D1B19",
        "sector": "#2A2724",
        "sectorHover": "#3A342E",
    },
}

_lock = threading.Lock()


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_app_dir()
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    cfg = _deep_merge(DEFAULT_CONFIG, data if isinstance(data, dict) else {})
    # Write defaults back once so the file is discoverable/editable.
    if not CONFIG_PATH.exists():
        try:
            CONFIG_PATH.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
    return cfg


def load_usage() -> dict[str, int]:
    ensure_app_dir()
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in data.items()}
    except Exception:
        return {}


def bump_usage(name: str) -> None:
    with _lock:
        usage = load_usage()
        usage[name] = usage.get(name, 0) + 1
        try:
            USAGE_PATH.write_text(
                json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
