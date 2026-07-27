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


def _scenario_dir(scenario: str) -> Path | None:
    """Resolve ``out/<skill>/<scenario>`` (M4b groups artifacts by skill, then scenario).

    Scenario slugs are globally unique across skills, so a bare scenario name still identifies one
    directory — the skill layer is transparent to callers, keeping every helper signature below
    unchanged. ``None`` if the scenario has not been generated yet.
    """
    return next((p for p in sorted(out_root().glob(f"*/{scenario}")) if p.is_dir()), None)


def load_summary(scenario: str) -> dict | None:
    """One scenario's ``out/<skill>/<scenario>/summary.json``, or ``None`` if not generated yet."""
    d = _scenario_dir(scenario)
    p = d / "summary.json" if d else None
    return json.loads(p.read_text(encoding="utf-8")) if p and p.is_file() else None


def scenario_names(skill: str | None = None) -> list[str]:
    """Scenario slugs that have a committed ``summary.json``, sorted.

    Pass ``skill`` to restrict to one skill's scenarios (``out/<skill>/*/``). The current Quarto
    site scopes itself to ``great-tables`` — its copy describes tables — while the frontend-design /
    pptx artifacts stay committed for the (deferred) multi-skill docs.
    """
    root = out_root()
    pattern = f"{skill}/*/summary.json" if skill else "*/*/summary.json"
    return sorted(p.parent.name for p in root.glob(pattern))


def read_text(scenario: str, *parts: str) -> str | None:
    """Read a committed artifact file (e.g. ``read_text(name, 'warm', 'table.py')``) or ``None``."""
    d = _scenario_dir(scenario)
    if d is None:
        return None
    p = d.joinpath(*parts)
    return p.read_text(encoding="utf-8") if p.is_file() else None


def _scroll(inner: str) -> str:
    """Wrap wide embedded content so it scrolls *within* its column instead of forcing horizontal
    page scroll or spilling past the "On this page" TOC. A native Great Tables table has many
    fixed-width columns and cannot reflow, so contain it rather than let it widen the layout."""
    return f'<div style="overflow-x:auto;max-width:100%">{inner}</div>'


def _embed_html(native: str, is_primary: bool = False) -> str:
    """Embed a committed HTML artifact in a panel.

    A full standalone document (a web skill's ``index.html``, with its own ``<html>`` and global CSS
    like ``*``/``body``) is sandboxed in an ``<iframe srcdoc>`` so its styles can't leak into — or
    reset — the surrounding docs page, and the cold/warm panels can't bleed into each other. A
    fragment (great-tables' ``table.html``, just a ``<table>``) is inlined and scrolled.

    ``is_primary`` marks the skill's own primary output (always a full document) — it is always
    sandboxed, regardless of the doctype sniff, so a long comment/preamble before ``<html>`` can't
    trick a full page into being inlined unsandboxed.
    """
    head = native.lstrip()[:256].lower()
    if is_primary or head.startswith("<!doctype") or "<html" in head:
        doc = _html.escape(native, quote=True)  # srcdoc attr value; the browser un-escapes to parse
        # `sandbox` (empty = most restrictive): the artifact is live-model-generated, so isolate
        # it — any <script>/inline handler is inert and gets a unique opaque origin, so it can't
        # reach the docs page's `parent.document`. The static HTML/CSS design still renders.
        return (
            f'<iframe srcdoc="{doc}" sandbox title="rendered output" loading="lazy" '
            'style="width:100%;height:520px;border:1px solid var(--bs-border-color,#ddd);'
            'border-radius:4px;background:#fff"></iframe>'
        )
    return _scroll(native)


def _panel_body(scenario: str, phase: str) -> str:
    """HTML for one before/after panel, per the scenario's skill.

    Renders, in order of preference: a self-contained HTML artifact natively (great-tables'
    ``table.html`` or a web skill's own ``index.html`` primary output); else a rendered PNG
    (``table.png``, embedded as a self-contained data URI since the committed images live outside
    ``docs/_site``); else the skill's **primary output** source (``table.py`` / ``deck.py`` / ...)
    as code. The primary artifact name comes from the committed ``summary.json`` (`output`), so a
    non-table skill no longer falls through to a missing ``table.py`` and shows "not generated".
    """
    primary = (load_summary(scenario) or {}).get("output", "table.py")
    # 1) native, self-contained HTML: a web skill's primary output, or great-tables' side table.html
    #    (a full document is sandboxed in an iframe; a table fragment is inlined — see _embed_html).
    html_names = ([primary] if primary.lower().endswith((".html", ".htm")) else []) + ["table.html"]
    for name in html_names:
        native = read_text(scenario, phase, name)
        if native and native.strip():
            return _embed_html(native, is_primary=(name == primary))
    # 2) a rendered raster: the primary output's sibling PNG (``plot.png`` for plotnine,
    #    ``table.png`` for great-tables), embedded as a self-contained data URI since the committed
    #    images live outside ``docs/_site``.
    d = _scenario_dir(scenario)
    if d is not None:
        stem_png = f"{primary.rsplit('.', 1)[0]}.png" if "." in primary else None
        for name in (stem_png, "plot.png", "table.png"):
            png = d / phase / name if name else None
            if png and png.is_file():
                b64 = base64.b64encode(png.read_bytes()).decode("ascii")
                return (f'<img alt="{phase}" style="max-width:100%;border-radius:8px" '
                        f'src="data:image/png;base64,{b64}">')
    # 3) the skill's primary output as code (e.g. deck.py for pptx, or table.py if HTML is missing)
    code = read_text(scenario, phase, primary)
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
    d = _scenario_dir(scenario)
    p = d / "recall.json" if d else None
    if not (p and p.is_file()):
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


def _pref_feedback_block(pref_meta: dict, pref_summary: dict | None) -> str:
    """One preference's quoted correction plus a concrete "when it stuck" statement.

    ``pref_meta`` is the raw preference mapping from the scenario YAML (has ``feedback``, the
    scripted natural-language correction); ``pref_summary`` is that same preference's entry from
    the committed ``summary.json`` (has ``runs_to_stick``/``cold_honored``), or ``None`` if the
    scenario hasn't been generated with a version of the runner that recorded it.
    """
    feedback = (pref_meta.get("feedback") or "").strip()
    html = f"<blockquote>&ldquo;{_html.escape(feedback)}&rdquo;</blockquote>" if feedback else ""
    if not pref_summary:
        return html
    runs_to_stick = pref_summary.get("runs_to_stick")
    if runs_to_stick is not None:
        note = f"This stuck starting at run {runs_to_stick} — honored from then on."
    else:
        note = "This hadn't stuck yet within the run budget shown here."
    if pref_summary.get("cold_honored"):
        prefix = "The cold run already happened to satisfy this by chance, but "
        note = prefix + note[0].lower() + note[1:]
    return html + f"<p><small>{_html.escape(note)}</small></p>"


def scenario_meta(scenario: str) -> dict | None:
    """The parsed scenario YAML (``harness/scenarios/<scenario>.yaml``) for one scenario slug.

    A thin per-scenario lookup over :func:`scenarios_meta`, the existing "read the committed YAML
    directly" loader (already used by the methodology table) — so the walkthrough's quoted user
    feedback comes from the same source of truth, not a paraphrase.
    """
    return next((m for m in scenarios_meta() if m.get("name") == scenario), None)


def triptych_html(scenario: str) -> str:
    """A 3-step guided walkthrough: what it produced, what wasn't good, what changed.

    Each step is a ``.ws-step`` inside a single-column ``.ws-steps`` (reusing the numbered-badge
    styling from ``docs/index.qmd``'s "how it works" section, forced to one column since each step
    here carries a full artifact panel), and each step also carries ``.ws-reveal`` individually —
    ``site.js`` observes every ``.ws-reveal`` element on its own, so the three steps fade in one at
    a time as the reader scrolls, rather than the whole group appearing together.

    1. **Here's what it produced** — the cold artifact (empty store).
    2. **Here's what wasn't good** — the scripted user correction(s), quoted verbatim from the
       scenario YAML's ``preferences[].feedback`` (not the raw recall/learned-layer dump), one per
       preference alongside a concrete "stuck starting at run N" statement from ``summary.json``.
    3. **Here's what changed** — the warm artifact (learned layer applied). The raw learned
       layer/recall payload is still available, demoted to a collapsed ``<details>`` — proof, not
       story.
    """
    meta = scenario_meta(scenario) or {}
    summary = load_summary(scenario) or {}
    prefs_summary = summary.get("preferences", {})
    prefs_meta = meta.get("preferences") or []
    feedback_html = "".join(
        _pref_feedback_block(p, prefs_summary.get(p.get("id", "")))
        for p in prefs_meta
    ) or "<em>no scripted feedback recorded for this scenario</em>"

    return (
        '<div class="ws-steps" style="grid-template-columns:1fr">'
        '<div class="ws-step ws-reveal">'
        '<div class="ws-step-title">Here&rsquo;s what it produced</div>'
        '<p class="ws-step-body">The skill runs against an <strong>empty</strong> Whetstone '
        "store — nothing has been taught yet.</p>"
        f"{_panel_body(scenario, 'cold')}"
        "</div>"
        '<div class="ws-step ws-reveal">'
        '<div class="ws-step-title">Here&rsquo;s what wasn&rsquo;t good</div>'
        '<p class="ws-step-body">The user corrects it, in their own words:</p>'
        f"{feedback_html}"
        "</div>"
        '<div class="ws-step ws-reveal">'
        '<div class="ws-step-title">Here&rsquo;s what changed</div>'
        '<p class="ws-step-body">The same task, generated again once the learned layer is '
        "applied.</p>"
        f"{_panel_body(scenario, 'warm')}"
        "<details><summary>Show the raw learned layer</summary>"
        f"{learned_layer_html(scenario)}</details>"
        "</div>"
        "</div>"
    )


def scenarios_meta(skill: str | None = None) -> list[dict]:
    """Parse the committed scenario YAMLs (``harness/scenarios/*.yaml``) for the methodology table.

    Reads the source of truth directly (only depends on the committed YAML), so the page shows
    exactly what was taught and how each "honored" check is decided — no dependency on a run. Pass
    ``skill`` to restrict to one skill (the current site shows ``great-tables`` only; see
    :func:`scenario_names`).
    """
    import yaml  # committed [showcase] dep

    root = out_root().parent / "scenarios"
    metas = []
    for path in sorted(root.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if skill and raw.get("skill") != skill:
            continue
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
