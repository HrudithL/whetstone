"""Helpers the Quarto pages use to read the harness's committed ``out/`` artifacts.

The site only ever *reads* ``harness/out/`` — it never regenerates it. Every loader tolerates
missing data so the site renders cleanly before the harness has been run (showing a "not generated
yet" note instead of erroring), and renders the real artifacts once ``python -m harness.run
--agent`` has populated ``out/``.
"""

from __future__ import annotations

import base64
import html as _html
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


def _panel_body(scenario: str, phase: str) -> str:
    """HTML for one table panel: native ``table.html`` if present, else a base64 PNG, else the code.

    PNGs are embedded as self-contained data URIs (the committed images live outside ``docs/_site``,
    so a relative path would not resolve in the deployed site).
    """
    native = read_text(scenario, phase, "table.html")
    if native:
        return native
    png = out_root() / scenario / phase / "table.png"
    if png.is_file():
        b64 = base64.b64encode(png.read_bytes()).decode("ascii")
        return f'<img alt="{phase} table" style="max-width:100%" src="data:image/png;base64,{b64}">'
    code = read_text(scenario, phase, "table.py")
    if code:
        return f"<pre><code>{_html.escape(code)}</code></pre>"
    return "<em>not generated</em>"


def learned_layer_html(scenario: str) -> str:
    """Render the verbatim ``recall.json`` payload (learnings + issues) for the middle panel."""
    p = out_root() / scenario / "recall.json"
    if not p.is_file():
        return "<em>not generated</em>"
    r = json.loads(p.read_text(encoding="utf-8"))

    def _items(entries: list, weighted: bool) -> str:
        rows = []
        for x in entries:
            w = x.get("weight")
            wt = f" · weight {w:.2f}" if weighted and isinstance(w, int | float) else ""
            rule = _html.escape(str(x.get("rule", "")))
            rows.append(
                f"<li><code>{x.get('id')}</code> <em>({_html.escape(str(x.get('scope')))}{wt})</em>"
                f"<br>{rule}</li>"
            )
        return "<ul>" + "".join(rows) + "</ul>"

    parts = []
    if r.get("learnings"):
        parts.append("<strong>Learnings</strong>" + _items(r["learnings"], True))
    if r.get("issues"):
        parts.append("<strong>Issues (mandatory)</strong>" + _items(r["issues"], False))
    return "".join(parts) or "<em>empty recall — nothing was retrieved</em>"


def triptych_html(scenario: str) -> str:
    """A three-column before / learned-layer / after block for one scenario."""
    return (
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;'
        'align-items:start;margin:0.5rem 0 2rem">'
        f'<div><h4>Before <small>(empty store)</small></h4>{_panel_body(scenario, "cold")}</div>'
        f'<div><h4>The learned layer <small>(verbatim recall)</small></h4>'
        f"{learned_layer_html(scenario)}</div>"
        f'<div><h4>After <small>(learned layer applied)</small></h4>'
        f'{_panel_body(scenario, "warm")}</div>'
        "</div>"
    )


def not_generated_note(what: str = "These panels"):
    """A Markdown callout shown when the harness hasn't populated ``out/`` yet."""
    from IPython.display import Markdown

    return Markdown(
        f"::: {{.callout-note}}\n## Not generated yet\n{what} populate after a real run of the "
        "showcase harness (`python -m harness.run --agent`). Until then the pipeline is verified "
        "with the free stub. See **Methodology** for how the artifacts are produced.\n:::"
    )
