"""Static matplotlib charts for the metrics dashboard (dataviz palette, light + dark).

Two charts, both built from the aggregated ``metrics.json``:

* **runs-to-stick** — a horizontal bar per preference (magnitude, one hue); a preference that never
  stuck is drawn as a muted hatched full-width bar labelled "didn't stick". Every bar is
  direct-labelled, so identity/value never depends on color alone.
* **value-over-time** — a line per learning (weight across warm runs), colored by the validated
  categorical order (fixed, never cycled); a legend plus a companion table give the relief the
  light-surface contrast WARN requires.

Each chart is rendered twice — once for the light surface, once for the dark — and returned as
inline SVG. ``charts_html`` wraps both with theme classes so the page shows the right one. Colors
are the reference dataviz palette, validated for both modes (see the dataviz skill).
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Reference dataviz palette (validated). Categorical hues in FIXED order per mode.
_CATEGORICAL = {
    "light": ["#2a78d6", "#008300", "#e87ba4", "#eda100",
              "#1baf7a", "#eb6834", "#4a3aa7", "#e34948"],
    "dark": ["#3987e5", "#008300", "#d55181", "#c98500",
             "#199e70", "#d95926", "#9085e9", "#e66767"],
}
_THEME = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "muted": "#52514e",
              "grid": "#f0efec", "accent": "#2a78d6"},
    "dark": {"surface": "#1a1a19", "ink": "#ffffff", "muted": "#c3c2b7",
             "grid": "#383835", "accent": "#3987e5"},
}


def _style(mode: str) -> dict:
    return _THEME[mode]


def _fig_to_svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)
    return buf.getvalue()


def _flat_prefs(metrics: dict) -> list[tuple[str, str, dict]]:
    """(scenario, pref_id, pref) for every preference, in scenario/pref order."""
    out = []
    for scenario, s in metrics.get("scenarios", {}).items():
        for pref_id, pref in s.get("preferences", {}).items():
            out.append((scenario, pref_id, pref))
    return out


def _runs_to_stick_svg(metrics: dict, mode: str) -> str:
    t = _style(mode)
    rows = _flat_prefs(metrics)
    labels = [f"{scn}\n{pid}" for scn, pid, _ in rows]
    fig, ax = plt.subplots(figsize=(7.5, max(2.0, 0.5 * len(rows) + 1)))
    y = range(len(rows))
    for i, (_, _, pref) in enumerate(rows):
        rts = pref.get("runs_to_stick")
        if rts is None:
            # Didn't stick: a muted hatched full-width bar with an explicit label (not color-alone).
            ax.barh(i, 1, color=t["grid"], edgecolor=t["muted"], hatch="///", height=0.62)
            ax.text(0.02, i, "didn't stick", va="center", ha="left", color=t["muted"], fontsize=9)
        else:
            ax.barh(i, rts, color=t["accent"], height=0.62)
            ax.text(rts, i, f" {rts}", va="center", ha="left", color=t["ink"], fontsize=10)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, color=t["ink"], fontsize=8)
    ax.set_xlabel("runs to stick (warm runs until re-applied without correction)", color=t["muted"])
    ax.set_title("Runs-to-stick per preference — lower is faster", color=t["ink"], loc="left")
    ax.invert_yaxis()
    _despine(ax, t)
    return _fig_to_svg(fig)


def _value_over_time_svg(metrics: dict, mode: str) -> str:
    t = _style(mode)
    hues = _CATEGORICAL[mode]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    series = 0
    for scn, pid, pref in _flat_prefs(metrics):
        if pref.get("polarity") != "learning":
            continue
        pts = [(v["run"], v["weight"]) for v in pref.get("value_over_time", [])
               if v.get("weight") is not None]
        if not pts:
            continue
        xs, ys = zip(*pts, strict=True)
        ax.plot(xs, ys, marker="o", markersize=5, linewidth=2,
                color=hues[series % len(hues)], label=f"{scn}/{pid}")
        series += 1
    if series == 0:
        ax.text(0.5, 0.5, "no weighted learnings recalled", ha="center", va="center",
                color=t["muted"], transform=ax.transAxes)
    else:
        ax.set_xlabel("warm run", color=t["muted"])
        ax.set_ylabel("learning weight", color=t["muted"])
        ax.set_ylim(0, 1)
        ax.legend(loc="lower right", fontsize=8, frameon=False, labelcolor=t["ink"])
    ax.set_title("Value over time — does the correction keep being valued?",
                 color=t["ink"], loc="left")
    _despine(ax, t)
    return _fig_to_svg(fig)


def _despine(ax, t: dict) -> None:
    ax.set_facecolor("none")
    ax.figure.set_facecolor("none")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(t["muted"])
    ax.tick_params(colors=t["muted"])
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def charts_html(metrics: dict) -> str:
    """Both charts, each in light + dark SVG, wrapped with theme classes for the page to swap."""
    blocks = []
    charts = (("runs-to-stick", _runs_to_stick_svg), ("value-over-time", _value_over_time_svg))
    for name, fn in charts:
        light = fn(metrics, "light")
        dark = fn(metrics, "dark")
        blocks.append(
            f'<figure class="viz-chart" aria-label="{name}">'
            f'<div class="chart-light">{light}</div>'
            f'<div class="chart-dark">{dark}</div>'
            "</figure>"
        )
    return "\n".join(blocks)
