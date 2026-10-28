# Third-party notices

Skill Wheel is Apache-2.0. It **bundles or depends on** the following
third-party components at runtime; their licenses apply to them, not to our code.

| Component | Version | License | Notes |
| --- | --- | --- | --- |
| PySide6 / Qt 6 | 6.7+ | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | Used dynamically (Qt DLLs); must remain replaceable |
| pynput | 1.7+ | LGPL-3.0 | Imported as a Python module |
| Python | 3.12 | PSF-2.0 | Bundled by PyInstaller when packaging an exe |

Full LGPL-3.0 text: [`LICENSES/LGPL-3.0.txt`](LICENSES/LGPL-3.0.txt).

## Packaging obligations (LGPL)

When distributing a packaged build (PyInstaller onefile, VSIX with a bundled exe):

1. Ship this notice and the LGPL text with the distribution.
2. Keep Qt/PySide6 dynamically loaded (`Qt6*.dll` extracted next to the exe or
   in `_internal`), and do not statically link or modify the libraries.
3. Tell recipients how to replace the LGPL libraries with their own compatible
   builds (replace the DLLs / site-packages directory and restart).
4. Do not add restrictions that forbid reverse engineering for debugging such
   replacements.

If you prefer a fully permissive distribution, use the commercial Qt license or
replace the Qt layer; Apache-2.0 alone does not relicense these dependencies.
