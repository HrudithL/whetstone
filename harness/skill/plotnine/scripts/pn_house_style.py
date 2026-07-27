"""
pn_house_style.py
-----------------
Shared visual-design helpers for building plots with `plotnine`. Import these into
every plot-building script so plots produced by this skill look and behave the same
way every time, regardless of the data source.

The point of centralizing this in one file instead of writing theme/palette calls
fresh in every script is consistency: the "house look" (base theme, gridlines, text
sizes, palette choice, figure size, dpi) is decided once, here, rather than
re-decided -- possibly differently -- on every request. To deviate for a specific
request (a color the user asked for, a different legend position), pass different
arguments to these helpers or skip them and call plotnine directly. Nothing here is
mandatory; it is a sensible, tested default.

The values here are the single source of truth that the `references/` files describe:
`big_color.md` documents the palettes returned by `house_palette()`,
`small_color.md` documents the theme/hexes applied by `apply_house_style()`, and
`geoms.md` documents the pinned mark defaults (`point_size`, `line_size`, the
`geom_jitter` `random_state`) applied directly in `geom_point()`/`geom_line()`/
`geom_jitter()` calls.

Usage:
    from pn_house_style import apply_house_style, house_palette, humanize_labels, save_plot, HOUSE_STYLE
"""
from __future__ import annotations

from plotnine import (
    element_blank,
    element_line,
    element_text,
    scale_color_cmap,
    scale_color_gradient2,
    scale_color_manual,
    scale_fill_cmap,
    scale_fill_gradient2,
    scale_fill_manual,
    theme,
    theme_minimal,
)

# ---------------------------------------------------------------------------
# Design tokens. This is the one place that defines the "house style" look.
# Change values here (or override per-call) rather than hard-coding one-off
# choices inside individual plot scripts. Mirrors references/small_color.md +
# big_color.md exactly.
# ---------------------------------------------------------------------------
HOUSE_STYLE = {
    "base_size": 12,
    # neutral hexes
    "gridline": "#E6E6E6",
    "text": "#222222",
    "background": "#FFFFFF",
    # the accent used when NO variable is color-encoded (big_color.md)
    "accent": "#2C6FB3",
    # text sizes (relative hierarchy: title > axis titles > ticks)
    "title_size": 15,
    "axis_title_size": 12,
    "axis_text_size": 10,
    "legend_title_size": 11,
    "legend_text_size": 10,
    # Big Color palettes
    "qualitative": [
        "#0072B2", "#E69F00", "#009E73", "#CC79A7",
        "#56B4E9", "#D55E00", "#F0E442", "#000000",
    ],  # Okabe-Ito, colorblind-safe
    "sequential_cmap": "viridis",
    "diverging_low": "#B2182B",
    "diverging_mid": "#F7F7F7",
    "diverging_high": "#2166AC",
    # frame
    "figure_size": (8, 5),
    "dpi": 200,
    "legend_position": "right",
    # mark defaults (geoms.md) -- pinned so a cold run never free-associates a
    # size; a taught preference (e.g. "make points bigger") overrides these
    # explicitly, it does not need to guess what the untaught default was.
    "point_size": 2,
    "line_size": 0.8,
    "jitter_random_state": 42,
}


def apply_house_style(p, *, legend_position: str | None = None, base_size: int | None = None):
    """Append the house theme (Small Color) to a ggplot object.

    Call this LAST, after all geoms/scales/labs are in place. Applies the base
    theme, gridline treatment, text sizes/color, figure size, and legend
    position from HOUSE_STYLE. Every argument is overridable per call, e.g.
    ``apply_house_style(p, legend_position="bottom")`` or
    ``apply_house_style(p, legend_position="none")`` for an un-grouped plot.
    """
    hs = HOUSE_STYLE
    legend_position = hs["legend_position"] if legend_position is None else legend_position
    base_size = hs["base_size"] if base_size is None else base_size
    return (
        p
        + theme_minimal(base_size=base_size)
        + theme(
            figure_size=hs["figure_size"],
            plot_title=element_text(size=hs["title_size"], weight="bold", color=hs["text"]),
            axis_title=element_text(size=hs["axis_title_size"], color=hs["text"]),
            axis_text=element_text(size=hs["axis_text_size"], color=hs["text"]),
            legend_title=element_text(size=hs["legend_title_size"], color=hs["text"]),
            legend_text=element_text(size=hs["legend_text_size"], color=hs["text"]),
            panel_grid_major=element_line(color=hs["gridline"], size=0.4),
            panel_grid_minor=element_blank(),
            legend_position=legend_position,
        )
    )


def house_palette(kind: str = "qualitative", *, aes: str = "color",
                  name: str | None = None, midpoint: float = 0.0, limits=None):
    """Return the house `scale_*` object for a Big Color data shape.

    kind:  "qualitative" (categorical), "sequential" (ordered magnitude),
           "diverging" (signed values around `midpoint`).
    aes:   "color" or "fill" -- which aesthetic the scale targets.
    name:  legend title (humanized). midpoint/limits only used for "diverging".
    See references/big_color.md for when to use each.
    """
    hs = HOUSE_STYLE
    if aes not in ("color", "fill"):
        raise ValueError("aes must be 'color' or 'fill'")

    if kind == "qualitative":
        fn = scale_color_manual if aes == "color" else scale_fill_manual
        return fn(values=hs["qualitative"], name=name)
    if kind == "sequential":
        fn = scale_color_cmap if aes == "color" else scale_fill_cmap
        return fn(cmap_name=hs["sequential_cmap"], name=name)
    if kind == "diverging":
        fn = scale_color_gradient2 if aes == "color" else scale_fill_gradient2
        kwargs = dict(low=hs["diverging_low"], mid=hs["diverging_mid"],
                      high=hs["diverging_high"], midpoint=midpoint, name=name)
        if limits is not None:
            kwargs["limits"] = limits
        return fn(**kwargs)
    raise ValueError(f"unknown kind {kind!r}; use qualitative|sequential|diverging")


def humanize_labels(*names: str, overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Turn raw column names into display labels for labs()/scale name=.

    Returns {raw_name: "Display Label"}. Automatic title-casing gets acronyms and
    units wrong, so pass overrides= for those (e.g. {"msrp": "MSRP", "hp": "Horsepower"}).
    Use only for VISIBLE labels -- keep original names inside aes()/scale_*.

        lab = humanize_labels("hp", "msrp", overrides={"msrp": "MSRP (USD)"})
        ... + labs(x=lab["hp"], y=lab["msrp"])
    """
    overrides = overrides or {}
    return {n: overrides.get(n, n.replace("_", " ").replace("-", " ").strip().title())
            for n in names}


def save_plot(p, path: str = "plot.png", *, width: float | None = None,
              height: float | None = None, dpi: int | None = None) -> str:
    """Save with the house figure size + dpi. The only renderer this skill uses.

    plotnine renders through matplotlib in-process (no browser). Do not call
    plt.show() or fall back to any HTML/PIL route.
    """
    hs = HOUSE_STYLE
    width = hs["figure_size"][0] if width is None else width
    height = hs["figure_size"][1] if height is None else height
    dpi = hs["dpi"] if dpi is None else dpi
    p.save(path, width=width, height=height, dpi=dpi, verbose=False)
    return path
