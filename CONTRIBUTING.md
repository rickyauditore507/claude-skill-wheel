# Contributing

Thanks for helping Skill Wheel.

## Development

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

.venv/Scripts/python.exe overlay/main.py --list
.venv/Scripts/python.exe overlay/main.py --demo --hover 2 --shot demo.png
```

Extension: plain JavaScript, no build step. Load it by copying `extension/` into
`~/.vscode/extensions/ricky.skill-wheel-<version>/` and reloading the window.

## Before a PR

- `python -m compileall overlay`
- `node --check extension/extension.js`
- Keep changes focused; describe the user-visible effect.

## Community catalog PRs

Add an entry to `catalog/index.json` following `docs/COMMUNITY_CATALOG.md`:
public repo only, metadata only, license required. No scraped personal data.

## License

By contributing you agree your work is licensed under Apache-2.0.
