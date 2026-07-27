# api.md — verified plotnine signatures (v0.15.7)

Condensed to the arguments you'll actually use. Verified against the installed
`plotnine==0.15.7`. Consult the live docs (https://plotnine.org/reference/) for anything
not covered. **A plot is one chained expression:** `p = ggplot(...) + geom_*(...) + ...`.

## Core

```python
from plotnine import ggplot, aes
ggplot(data=None, mapping=None)          # ggplot(df, aes("x", "y", color="grp"))
aes(x=None, y=None, **kwargs)            # color=, fill=, group=, shape=, size=, alpha=
```
- Map a variable **inside** `aes()` → it gets a scale + legend. Set an aesthetic as a
  **constant** (outside `aes()`, e.g. `geom_point(color="#2C6FB3")`) → no legend.
- Use **original column names** in `aes()`, not humanized labels.

## Geoms (all take `mapping=`, `data=`, plus `**kwargs` for constants/params)

```python
geom_point(alpha=, size=, color=)                 # scatter; ALWAYS pass size=HOUSE_STYLE["point_size"]
                                                   # explicitly -- plotnine has no size of its own
                                                   # worth trusting, and omitting size= silently falls
                                                   # back to plotnine's own (unpinned) default, not this one
geom_jitter(width=, height=, alpha=, random_state=)  # jittered points (discrete/rounded x);
                                                      # random_state is MANDATORY -- ALWAYS pass
                                                      # random_state=HOUSE_STYLE["jitter_random_state"]
                                                      # explicitly, never unseeded
geom_line(size=, color=)                          # trend; pair with geom_point(); ALWAYS pass
                                                   # size=HOUSE_STYLE["line_size"] explicitly -- same
                                                   # reasoning as geom_point above
geom_col()                                        # bars from a y value (stat="identity")
geom_bar()                                        # bars as counts of rows (stat="count")
geom_histogram(bins=30)                           # ALWAYS pass bins
geom_density(alpha=0.5)
geom_boxplot() / geom_violin()
geom_tile()                                       # heatmap; aes(fill=value)
geom_smooth(method="lm", se=True)                 # trend line overlay
```

## Scales — palettes (see big_color.md for which)

```python
scale_color_manual(values=[...], name="Legend title")     # qualitative; scale_fill_manual too
scale_color_cmap(cmap_name="viridis", name=...)           # continuous sequential; scale_fill_cmap
scale_color_cmap_d(cmap_name="viridis")                   # discrete ordered
scale_fill_gradient2(low="#B2182B", mid="#F7F7F7", high="#2166AC",
                     midpoint=0, limits=(-b, b), name=...) # diverging, symmetric
```

## Scales — axes (number & date formatting)

```python
from mizani.labels import label_comma, label_currency, label_percent, label_date
scale_y_continuous(name=None, breaks=True, limits=None, labels=label_comma(), trans=None)
scale_x_continuous(..., trans="log10")            # log axis
scale_y_continuous(labels=label_currency(prefix="$", precision=0))
scale_y_continuous(labels=label_percent())        # expects 0–1 fractions
scale_x_date(date_breaks=..., date_labels=...)         # x must be real datetimes -- pick the
                                                        # pair from the span table below, never eyeball it
```

### Date-axis defaults (pinned by span — never a freehand "readable ticks" guess)

Compute the span (`max(date) - min(date)`) from the already-parsed datetime column
(`data.md`), then pick the matching row — this is a data-driven branch, not a
free choice:

| Data span | `date_breaks` | `date_labels` |
|---|---|---|
| ≤ 90 days | `"2 weeks"` | `"%b %d, %Y"` |
| > 90 days and ≤ 2 years | `"2 months"` | `"%b %Y"` |
| > 2 years | `"1 year"` | `"%Y"` |

Boundaries are non-overlapping by construction (`≤`/`>` on each edge) — a span of
exactly 90 days always falls in the first row, never both. The short-span format
always includes the year (`%Y`) even though the tick spacing is tight — the
mandated trend title (`geoms.md`, `"{Y} over time"`) carries no date range of its
own, so omitting the year from the ticks would make a plot's period genuinely
ambiguous across a year boundary, not just visually redundant.

## Labels, facets, coords

```python
from plotnine import labs, facet_wrap, facet_grid, coord_flip
labs(title=, subtitle=, x=, y=, color=, fill=, caption=)   # title + x + y REQUIRED
facet_wrap("~col", ncol=None, scales="fixed")              # "free"/"free_x"/"free_y"
facet_grid("row~col")
coord_flip()                                               # horizontal bars
```

## Theme

```python
from plotnine import theme, theme_minimal, element_text, element_line, element_blank
theme_minimal(base_size=12)                # base theme (house default)
theme(
    figure_size=(8, 5),
    plot_title=element_text(size=15, weight="bold", color="#222222"),
    axis_title=element_text(size=12, color="#222222"),
    axis_text=element_text(size=10, color="#222222"),
    panel_grid_major=element_line(color="#E6E6E6", size=0.4),
    panel_grid_minor=element_blank(),
    legend_position="right",               # "right" | "bottom" | "none"
)
```
`element_text` args: `family`, `style`, `weight` (`"bold"`/int), `color`, `size`, `ha`, `va`.

## Save (the only renderer)

```python
p.save("plot.png", width=8, height=5, dpi=200, verbose=False)
```
- Renders through matplotlib in-process — no browser. Never `plt.show()`, never write HTML
  or fall back to PIL. If it errors, surface the error verbatim.
