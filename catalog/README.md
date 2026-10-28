# Community catalog index

`index.json` is the curated list of **public** Claude Code skills the wheel can offer.

Rules:

- Public repositories only (GitHub). No private repos, no personal profiles, no scraped user data.
- Metadata only: name, description, repo, path, ref, license, source_url, tags.
- The `path` must point at a `SKILL.md` under a `skills/` directory.
- `license` must be an SPDX id; permissive licenses are imported without extra flags.
- Imports are explicit and always show source + license first.

Add an entry with a PR. Schema and safety checklist: `docs/COMMUNITY_CATALOG.md`.

Example entry:

```json
{
  "name": "example-skill",
  "description": "One sentence about what it does.",
  "repo": "owner/repo",
  "path": ".claude/skills/example-skill/SKILL.md",
  "ref": "main",
  "license": "MIT",
  "source_url": "https://github.com/owner/repo/blob/main/.claude/skills/example-skill/SKILL.md",
  "tags": ["example"]
}
```
