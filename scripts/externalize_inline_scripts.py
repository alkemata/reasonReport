#!/usr/bin/env python3
"""Move executable inline scripts in generated JupyterLite HTML to .js files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SCRIPT_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
META_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE | re.DOTALL)
JUPYTERLITE_CSP = (
    "default-src 'self' data: blob:; "
    "script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; "
    "worker-src 'self' blob:; "
    "connect-src 'self' https://cdn.jsdelivr.net; frame-src 'self'; "
    "img-src 'self' data: blob:; font-src 'self' data:"
)
NON_EXECUTABLE_TYPES = {
    "application/json",
    "application/ld+json",
    "importmap",
    "speculationrules",
}


def attribute_value(attributes: str, name: str) -> str | None:
    match = re.search(
        rf"\b{re.escape(name)}\s*=\s*(['\"])(.*?)\1",
        attributes,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(2).strip().lower() if match else None


def externalize(html_path: Path) -> int:
    html = html_path.read_text(encoding="utf-8")
    script_number = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal script_number
        attributes = match.group("attrs")
        body = match.group("body")
        script_type = attribute_value(attributes, "type")
        if re.search(r"\bsrc\s*=", attributes, re.IGNORECASE):
            return match.group(0)
        if script_type in NON_EXECUTABLE_TYPES or not body.strip():
            return match.group(0)

        script_number += 1
        script_name = f"csp-inline-{script_number}.js"
        (html_path.parent / script_name).write_text(body.strip() + "\n", encoding="utf-8")
        return f'<script{attributes} src="./{script_name}"></script>'

    updated = SCRIPT_RE.sub(replace, html)

    def replace_csp(match: re.Match[str]) -> str:
        tag = match.group(0)
        if attribute_value(tag, "http-equiv") != "content-security-policy":
            return tag
        return (
            '<meta http-equiv="Content-Security-Policy" '
            f'content="{JUPYTERLITE_CSP}">'
        )

    updated = META_RE.sub(replace_csp, updated)
    if updated != html:
        html_path.write_text(updated, encoding="utf-8")
    return script_number


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path, help="Generated JupyterLite output directory")
    args = parser.parse_args()
    total = sum(externalize(path) for path in args.site.rglob("*.html"))
    print(f"Externalized {total} executable inline JupyterLite script(s)")


if __name__ == "__main__":
    main()
