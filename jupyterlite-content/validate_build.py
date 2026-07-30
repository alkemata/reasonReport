"""Fail an image build with a precise message when JupyterLite is incomplete."""

import json
import sys
from pathlib import Path


root = Path(sys.argv[1])
required = (
    root / "api/contents/all.json",
    root / "static/pyodide/pyodide.js",
    # JupyterLite 0.6 emits the user wheel index at the site root. It is not a
    # Contents API resource, so it deliberately does not live below ``api``.
    root / "pypi/all.json",
    root / "jupyter-lite.json",
)
missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"JupyterLite build is missing required files: {', '.join(missing)}")

pypi_index = (root / "pypi/all.json").read_text(encoding="utf-8")
if "comm-0.2.2-py3-none-any.whl" not in pypi_index:
    raise SystemExit("JupyterLite piplite index does not contain comm 0.2.2")

config = json.loads((root / "jupyter-lite.json").read_text(encoding="utf-8"))
pyodide_settings = (
    config.get("jupyter-config-data", {})
    .get("litePluginSettings", {})
    .get("@jupyterlite/pyodide-kernel-extension:kernel", {})
)
if pyodide_settings.get("pyodideUrl") != "./static/pyodide/pyodide.js":
    raise SystemExit("JupyterLite pyodideUrl does not point to the bundled runtime")
