"""Fail an image build with a precise message when JupyterLite is incomplete."""

import json
import sys
from pathlib import Path


root = Path(sys.argv[1])
required = (
    root / "api/contents/all.json",
    root / "static/pyodide/pyodide.js",
    root / "api/pypi/all.json",
    root / "jupyter-lite.json",
)
missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"JupyterLite build is missing required files: {', '.join(missing)}")

pypi_index = (root / "api/pypi/all.json").read_text(encoding="utf-8")
if "comm-0.2.2-py3-none-any.whl" not in pypi_index:
    raise SystemExit("JupyterLite piplite index does not contain comm 0.2.2")

config = json.loads((root / "jupyter-lite.json").read_text(encoding="utf-8"))
if config.get("jupyter-config-data", {}).get("pyodideUrl") != "./static/pyodide/pyodide.js":
    raise SystemExit("JupyterLite pyodideUrl does not point to the bundled runtime")
