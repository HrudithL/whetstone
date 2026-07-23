#!/usr/bin/env python3
"""Generate llms.txt + llms-full.txt for the great-docs site.

Workaround for an upstream great-docs gap: its landing template links llms.txt / llms-full.txt
unconditionally, but great-docs only writes those files when the package has a populated
`api-reference` section. Whetstone exposes an MCP tool reference (not a Python api-reference), so
great-docs emits the links but never the files -> dead links (GREAT_DOCS_SPIKE.md, Gap 2).

We synthesize both files from the build's own `.well-known/mcp.json` (tool names + descriptions) so
they stay accurate without hand-maintenance. Run after `great-docs build`, pointed at the built
great-docs/_site directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_URL = "https://hrudithl.github.io/whetstone/docs/"


def first_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def main(site_dir: str) -> int:
    site = Path(site_dir)
    manifest = site / ".well-known" / "mcp.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    server = data.get("server", {})
    name = server.get("name", "whetstone")
    desc = server.get("description", "")
    tools = data.get("capabilities", {}).get("tools", {}).get("list", [])

    # llms.txt — a concise index (llms.txt standard: H1 + blockquote + link sections).
    idx = [f"# {name}", "", f"> {desc}", "", "## MCP tools", ""]
    for t in tools:
        tname = t["name"]
        summary = first_line(t.get("description", ""))
        idx.append(f"- [{tname}]({BASE_URL}reference/mcp/{tname}.html): {summary}")
    idx += [
        "",
        "## Docs",
        "",
        f"- [Overview]({BASE_URL})",
        f"- [Contributing]({BASE_URL}contributing.html)",
        f"- [License]({BASE_URL}license.html)",
        "",
    ]
    (site / "llms.txt").write_text("\n".join(idx), encoding="utf-8")

    # llms-full.txt — the same index plus each tool's full description text.
    full = [f"# {name}", "", f"> {desc}", "", "## MCP tools", ""]
    for t in tools:
        full += [f"### {t['name']}", "", t.get("description", "").strip(), ""]
    (site / "llms-full.txt").write_text("\n".join(full), encoding="utf-8")

    print(f"Wrote {site/'llms.txt'} and {site/'llms-full.txt'} ({len(tools)} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "great-docs/_site"))
