"""Helpers the Quarto pages use to read the harness's committed ``out/`` artifacts.

The site only ever *reads* ``harness/out/`` — it never regenerates it. Every loader tolerates
missing data so the site renders cleanly before the harness has been run (showing a "not generated
yet" note instead of erroring), and renders the real artifacts once ``python -m harness.run
--agent`` has populated ``out/``.
"""

from __future__ import annotations

import json
from pathlib import Path


def out_root() -> Path:
    """Locate ``harness/out`` by walking up from the current working directory."""
    for base in [Path.cwd(), *Path.cwd().parents]:
        cand = base / "harness" / "out"
        if cand.is_dir():
            return cand
    return Path.cwd() / "harness" / "out"


def load_metrics() -> dict | None:
    """The aggregated ``out/metrics.json`` document, or ``None`` if not generated yet."""
    p = out_root() / "metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def load_summary(scenario: str) -> dict | None:
    """One scenario's ``out/<scenario>/summary.json``, or ``None`` if not generated yet."""
    p = out_root() / scenario / "summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def scenario_names() -> list[str]:
    """Scenario slugs that have a committed ``summary.json``, sorted."""
    root = out_root()
    return sorted(p.parent.name for p in root.glob("*/summary.json"))


def read_text(scenario: str, *parts: str) -> str | None:
    """Read a committed artifact file (e.g. ``read_text(name, 'warm', 'table.py')``) or ``None``."""
    p = out_root().joinpath(scenario, *parts)
    return p.read_text(encoding="utf-8") if p.is_file() else None


def not_generated_note(what: str = "These panels"):
    """A Markdown callout shown when the harness hasn't populated ``out/`` yet."""
    from IPython.display import Markdown

    return Markdown(
        f"::: {{.callout-note}}\n## Not generated yet\n{what} populate after a real run of the "
        "showcase harness (`python -m harness.run --agent`). Until then the pipeline is verified "
        "with the free stub. See **Methodology** for how the artifacts are produced.\n:::"
    )
