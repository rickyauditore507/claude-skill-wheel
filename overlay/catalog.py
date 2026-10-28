"""Community skill catalog: public metadata only, explicit imports.

Design and safety rules live in docs/COMMUNITY_CATALOG.md. This module never
downloads a skill body unless the caller explicitly asks to import one.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from config import APP_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "catalog" / "index.json"
CACHE_PATH = APP_DIR / "catalog-cache.json"

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

PERMISSIVE_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "CC0-1.0", "Unlicense", "0BSD", "MPL-2.0",
}

MAX_SKILL_BYTES = 200_000


@dataclass
class CatalogEntry:
    name: str
    description: str
    repo: str
    path: str
    ref: str = "main"
    license: str = ""
    source_url: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def raw_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.ref}/{self.path.lstrip('/')}"

    @property
    def permissive(self) -> bool:
        return self.license in PERMISSIVE_LICENSES

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description, "repo": self.repo,
            "path": self.path, "ref": self.ref, "license": self.license,
            "source_url": self.source_url or self.raw_url, "tags": self.tags,
        }


def _validate(raw: dict) -> tuple[CatalogEntry | None, str]:
    name = str(raw.get("name", "")).strip().lower()
    desc = str(raw.get("description", "")).strip()
    repo = str(raw.get("repo", "")).strip()
    path = str(raw.get("path", "")).strip()
    ref = str(raw.get("ref", "main")).strip() or "main"
    lic = str(raw.get("license", "")).strip()
    src = str(raw.get("source_url", "")).strip()
    tags = [str(t) for t in (raw.get("tags") or []) if str(t).strip()]

    if not NAME_RE.match(name):
        return None, f"bad name: {name!r}"
    if not desc or len(desc) > 300:
        return None, f"bad description for {name}"
    if not REPO_RE.match(repo):
        return None, f"bad repo for {name}: {repo!r}"
    if not path.endswith("SKILL.md") or "/skills/" not in path:
        return None, f"bad path for {name}: {path!r}"
    if ".." in path.split("/") or ".." in ref.split("/") or path.startswith("/"):
        return None, f"unsafe path/ref for {name}"
    if src:
        host = urllib.parse.urlparse(src).hostname or ""
        if not host.endswith("github.com"):
            return None, f"source_url host not github for {name}"
    return CatalogEntry(name=name, description=desc, repo=repo, path=path,
                        ref=ref, license=lic, source_url=src, tags=tags), ""


def load_index(index_url: str = "", index_path: str = "") -> tuple[list[CatalogEntry], list[str]]:
    """Read the curated index (local file first, optional HTTPS URL)."""
    data: dict = {}
    errors: list[str] = []
    source = Path(index_path) if index_path else DEFAULT_INDEX

    if index_url:
        try:
            cached = _read_cache(index_url)
            if cached is not None:
                data = cached
            else:
                with urllib.request.urlopen(index_url, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                _write_cache(index_url, data)
        except Exception as exc:
            errors.append(f"fetch {index_url}: {exc}")
            data = {}
    elif source.exists():
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"read {source}: {exc}")

    entries: list[CatalogEntry] = []
    seen: set[str] = set()
    for raw in (data.get("entries") or []):
        if not isinstance(raw, dict):
            continue
        entry, err = _validate(raw)
        if entry is None:
            errors.append(err)
            continue
        if entry.name in seen:
            errors.append(f"duplicate: {entry.name}")
            continue
        seen.add(entry.name)
        entries.append(entry)
    entries.sort(key=lambda e: (e.name, e.repo))
    return entries, errors


def _read_cache(url: str) -> dict | None:
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if data.get("url") == url and time.time() - float(data.get("fetched_at", 0)) < 24 * 3600:
            return data.get("index") or {}
    except Exception:
        return None
    return None


def _write_cache(url: str, index: dict) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(
            {"url": url, "fetched_at": time.time(), "index": index},
            ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def search(entries: list[CatalogEntry], query: str) -> list[CatalogEntry]:
    q = query.lower().strip()
    if not q:
        return entries
    return [e for e in entries
            if q in e.name or q in e.description.lower()
            or any(q in t.lower() for t in e.tags)]


def import_entry(entry: CatalogEntry, allow_license: bool = False) -> Path:
    """Download one SKILL.md after the caller has confirmed. Returns its path."""
    if not entry.permissive and not allow_license:
        raise PermissionError(f"{entry.name}: license {entry.license or 'unknown'} is not permissive")
    if not entry.raw_url.startswith("https://raw.githubusercontent.com/"):
        raise ValueError("refusing non-github raw url")
    with urllib.request.urlopen(entry.raw_url, timeout=10) as resp:
        body = resp.read(MAX_SKILL_BYTES + 1)
    if len(body) > MAX_SKILL_BYTES:
        raise ValueError("skill file too large")
    text = body.decode("utf-8", errors="replace")
    if not text.lstrip().startswith("---"):
        raise ValueError("not a SKILL.md (missing frontmatter)")

    target_dir = Path.home() / ".claude" / "skills" / entry.name
    if target_dir.exists():
        raise FileExistsError(f"{target_dir} already exists")
    target_dir.mkdir(parents=True)
    target = target_dir / "SKILL.md"
    target.write_text(text, encoding="utf-8")
    return target
