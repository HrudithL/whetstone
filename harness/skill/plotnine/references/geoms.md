# geoms.md — map the question to ONE geom family

Pick the geom from **what the user is asking**, not from what looks nice. Find the row,
use that geom, apply its knobs. One primary geom family per plot; add a secondary layer
(e.g. `geom_smooth` on a scatter) only when it answers the same question.

## The form-decision table

| The question is about… | Primary geom | Notes / knobs |
|---|---|---|
| **Relationship** between two numeric vars | `geom_point()` | add `geom_smooth(method="lm")` for a trend; group → `color=` |
| **Ranking / amount** across categories (pre-aggregated) | `geom_col()` | `stat="identity"`; sort bars (see below); horizontal for long labels |
| **Frequency** of raw categories | `geom_bar()` | counts rows itself (`stat="count"`) |
| **Trend over time** / ordered x | `geom_line()` | often `+ geom_point()`; one line per group via `color=`/`group=` |
| **Distribution** of one numeric var | `geom_histogram(bins=...)` or `geom_density()` | always set `bins`; density for a smooth shape |
| **Compare distributions** across groups | `geom_boxplot()` or `geom_violin()` | `x=` the group, `y=` the value |
| **Part-of-whole** across categories | `geom_col(position="stack")` or `"fill"` | `"fill"` = proportions (0–1 y axis) |
| **Two categoricals + one value** (matrix) | `geom_tile(aes(fill=value))` | this is the heatmap; sequential/diverging fill |

## Bars: the details that make them look intentional

- **Sort by value**, not alphabetically. Set an ordered categorical on the category column
  *after* sorting, or reverse for horizontal bars:
  ```python
  order = agg.sort_values("total", ascending=True)["region"].tolist()
  agg["region"] = pd.Categorical(agg["region"], categories=order, ordered=True)
  ```
- **Long category labels** → make it horizontal with `+ coord_flip()`.
- `geom_col` for values you computed; `geom_bar` for raw counts. Don't use `geom_bar` with
  a `y` aesthetic — that's `geom_col`'s job.

## Overplotting (dense scatters)

Many overlapping points hide the data. In order of preference:
1. `geom_point(alpha=0.3)` — cheapest fix.
2. `geom_jitter(width=..., height=...)` when x or y is discrete/rounded.
3. `geom_bin2d()` or `geom_density_2d()` for very dense clouds (thousands of points).

## Distributions: pick deliberately

- **Histogram** — you care about counts in bins; always pass an explicit `bins=` (25–40 is
  a sane default) rather than the plotnine default warning.
- **Density** — you care about the smooth shape; good for comparing 2–3 groups with `fill=`
  and `alpha=0.5`.
- **Boxplot** — comparing many groups' spread/median compactly.
- **Violin** — like boxplot but shows the full distribution shape per group.

## Facets vs. color

- Encode a **grouping** variable with `color=`/`fill=` when the groups overlap in the same
  panel and you want them compared directly (≤ ~6 groups).
- Use **facets** (`facet_wrap("~col")` / `facet_grid("row~col")`) when there are many groups
  or the overlap is unreadable — small multiples beat a rainbow of 12 lines.
