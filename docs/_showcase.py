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


def _scroll(inner: str) -> str:
    """Wrap wide embedded content so it scrolls *within* its column instead of forcing horizontal
    page scroll or spilling past the "On this page" TOC. A native Great Tables table has many
    fixed-width columns and cannot reflow, so contain it rather than let it widen the layout."""
    return f'<div style="overflow-x:auto;max-width:100%">{inner}</div>'


def _panel_body(scenario: str, phase: str) -> str:
    """HTML for one table panel: native ``table.html`` if present, else a base64 PNG, else the code.

    PNGs are embedded as self-contained data URIs (the committed images live outside ``docs/_site``,
    so a relative path would not resolve in the deployed site).
    """
    native = read_text(scenario, phase, "table.html")
    if native and native.strip():
        return _scroll(native)
    png = out_root() / scenario / phase / "table.png"
    if png.is_file():
        b64 = base64.b64encode(png.read_bytes()).decode("ascii")
        return f'<img alt="{phase} table" style="max-width:100%" src="data:image/png;base64,{b64}">'
    code = read_text(scenario, phase, "table.py")
    if code:
        return _scroll(f"<pre><code>{_html.escape(code)}</code></pre>")
    return "<em>not generated</em>"


def learned_layer_html(scenario: str) -> str:
    """Render the middle panel: the **exact learned-layer text injected into the warm prompt**.

    ``learned_layer.txt`` is the literal string the runner fed the model (from
    ``format_learned_layer``), so it is precisely "what the model was told". If it is absent (older
    runs), fall back to the raw ``recall.json`` and say so, rather than misclaiming the prompt text.
    """
    injected = read_text(scenario, "learned_layer.txt")
    if injected and injected.strip():
        return (
            "<p><small>The learned layer injected into the warm run's prompt, verbatim:</small></p>"
            "<pre style='max-height:32rem;overflow:auto;white-space:pre-wrap;"
            f"overflow-wrap:anywhere'><code>{_html.escape(injected)}</code></pre>"
        )
    p = out_root() / scenario / "recall.json"
    if not p.is_file():
        return "<em>not generated</em>"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not raw.get("learnings") and not raw.get("issues"):
        return "<em>empty recall — nothing was retrieved</em>"
    pretty = json.dumps(raw, indent=2, ensure_ascii=False)
    return (
        "<p><small>The stored <code>recall()</code> data (source of the injected layer):</small>"
        "</p><pre style='max-height:32rem;overflow:auto;white-space:pre-wrap;"
        f"overflow-wrap:anywhere'><code>{_html.escape(pretty)}</code></pre>"
    )


def triptych_html(scenario: str) -> str:
    """Before / after tables side by side, with the learned layer full-width beneath them.

    ``minmax(0,1fr)`` + ``min-width:0`` on the children let the two table columns shrink below their
    content's intrinsic width so a wide table scrolls inside its own panel (via ``_scroll``) instead
    of widening the grid past the page / TOC. The learned layer sits below at full width, where its
    injected text has room to wrap rather than run off to the right."""
    return (
        '<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:1rem;'
        'align-items:start;margin:0.5rem 0 1rem">'
        f'<div style="min-width:0"><h4>Before <small>(empty store)</small></h4>'
        f'{_panel_body(scenario, "cold")}</div>'
        f'<div style="min-width:0"><h4>After <small>(learned layer applied)</small></h4>'
        f'{_panel_body(scenario, "warm")}</div>'
        "</div>"
        '<div style="min-width:0;margin:0 0 2rem">'
        '<h4>The learned layer <small>(injected into the warm run, verbatim)</small></h4>'
        f"{learned_layer_html(scenario)}</div>"
    )


def scenarios_meta() -> list[dict]:
    """Parse the committed scenario YAMLs (``harness/scenarios/*.yaml``) for the methodology table.

    Reads the source of truth directly (only depends on the committed YAML), so the page shows
    exactly what was taught and how each "honored" check is decided — no dependency on a run.
    """
    import yaml  # committed [showcase] dep

    root = out_root().parent / "scenarios"
    metas = []
    for path in sorted(root.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        metas.append(raw)
    return metas


def not_generated_note(what: str = "These panels"):
    """A Markdown callout shown when the harness hasn't populated ``out/`` yet."""
    from IPython.display import Markdown

    return Markdown(
        f"::: {{.callout-note}}\n## Not generated yet\n{what} populate after a real run of the "
        "showcase harness (`python -m harness.run --agent`). Until then the pipeline is verified "
        "with the free stub. See **Methodology** for how the artifacts are produced.\n:::"
    )
