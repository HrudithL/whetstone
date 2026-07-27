#!/usr/bin/env python3
"""Correct two fabricated/inaccurate fields in the great-docs-generated mcp.json manifest.

Workaround for two upstream great-docs gaps (GREAT_DOCS_NATIVE_GAPS.md, Bug B1):

1. `installation.install` is hard-coded by great-docs to `pip install {package}[mcp]`
   (great_docs/_mcp_docs.py::generate_mcp_manifest) regardless of whether that extra exists.
   Whetstone has no `[mcp]` extra (`pyproject.toml` defines dev/embeddings/showcase/docs) -- running
   the advertised command prints a pip warning about a nonexistent extra.
2. `server.run` is hard-coded to `{"command": "python", "args": ["-m", <module>]}`. That technically
   works but doesn't reflect the documented, intended install path -- the `whetstone-mcp` /
   `whetstone` console-script entry points (`pyproject.toml` [project.scripts]), the same command
   the human docs (README.md / docs/install.qmd) tell users and MCP hosts to run.

There is no great-docs config override for either field (checked great_docs 0.15.0's `config.py` mcp
schema and `core.py::_generate_mcp_manifest`, which never passes `install_command` through), so we
patch the manifest in place after `great-docs build`, mirroring the approach the deleted
`gen_llms_txt.py` used for a different upstream gap.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_NAME = "whetstone-mcp"
CONSOLE_SCRIPT = "whetstone-mcp"


def main(site_dir: str) -> int:
    site = Path(site_dir)
    manifest_path = site / ".well-known" / "mcp.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    installation = data.setdefault("installation", {})
    installation["package"] = PACKAGE_NAME
    installation["install"] = f"pip install {PACKAGE_NAME}"

    server = data.setdefault("server", {})
    server["run"] = {"command": CONSOLE_SCRIPT, "args": []}

    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Fixed installation.install + server.run in {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "great-docs/_site"))
