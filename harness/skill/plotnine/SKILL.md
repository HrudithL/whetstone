---
name: plotnine
description: Use when the user's request involves building any plot, chart, or data visualization with `plotnine`, `ggplot`, the grammar of graphics in Python, or turning tabular data (CSV, DataFrame, spreadsheet) into a rendered plot PNG. Drives every plot through one deterministic 6-step flowchart — understand data, choose the form (geom), Big Color (≤1 color-encoded variable), scales & labels, Small-Color/theme checklist, render+verify — so the same input characteristics always produce the same publication-ready chart. Before writing any Python, read `references/REFERENCE.md`: it routes every geom, palette, theme, and API decision to the exact reference file that pins its value. The mandatory renderer is `p.save("plot.png", ...)`. Invoke before reading the data or writing any Python — the flowchart shapes the whole script.
---

# plotnine Skill

Build publication-ready plots in Python with `plotnine` (the grammar of graphics).
This skill is a **flowchart, not a menu**: for every part of a plot there is one
deterministic rule (or one explicit, data-driven branch), so the **same input always
produces the same output**. **Every plot reads as one finished product.**

## Read this before you write ANY Python

Before you write **any** Python, read **`references/REFERENCE.md`**. It is the single
doorway that routes every decision below to the exact reference file holding its
pinned value — geom choice, palette, hex, theme token, `save()` dpi/size, method
signature, worked example. **Do not skip it.** SKILL.md carries the *procedure and the
decision points*; it deliberately holds **zero** pinned values. Those live only in the
references that `REFERENCE.md` points you to.

## Rule 0 — the user's prompt overrides everything

Every rule below is a **default**. Any explicit instruction in the user's prompt wins
(a requested geom, a specific color, "log the y axis," "facet by region," "no legend").
The flowchart decides what to do *in the absence of* an instruction; it never overrides
one. When a user instruction conflicts with a default, follow the user and drop the
conflicting default silently — do not fight it or add it back later.

## The 6-step flowchart

```
1. UNDERSTAND THE DATA   grain? measures? categories? time? units? quality?
                         clean → ONE correctly-typed, TIDY (long) DataFrame (references/data.md)
                         validate request vs data (refuse the unanswerable, don't fake it)
2. CHOOSE THE FORM       map the QUESTION to ONE geom family, with its PINNED mark size
                         (references/geoms.md): relationship → point · ranking/amount →
                         bar/col (HARD BRANCH: horizontal/coord_flip ranking → the TALL
                         figure size, never the landscape default — see Global constants) ·
                         trend → line · distribution → histogram/density/boxplot ·
                         part-of-whole → bar
3. BIG COLOR             ≤ 1 color-encoded variable = the hero aesthetic; palette chosen
                         by DATA SHAPE (references/big_color.md): categorical → qualitative,
                         ordered magnitude → sequential, signed → diverging. No hero
                         variable → a single house accent, no legend.
4. SCALES & LABELS       axis transforms/limits · TEMPLATED title (references/geoms.md) +
                         axis labels WITH UNITS · legend title · pinned date-axis
                         breaks/labels by span, number formatting (references/api.md, geoms.md)
5. SMALL COLOR / THEME   fixed checklist: base theme · panel background · gridlines ·
                         text sizes · legend position · figure size + dpi — confirm the
                         Step 2 tall-figure-size branch was applied if it fired
                         (references/small_color.md)
6. RENDER & VERIFY       p.save("plot.png", ...) · read it back · audit every rule
```

The order is fixed: the geom (Step 2) is chosen before color (Step 3), and color intent
(Step 3) is decided before the quiet theme polish (Step 5).

## Withhold values, forbid guessing — open the file the action needs

SKILL.md names *what* to decide; the *value* you type lives only in a reference file.
Before you type the code below, open the file `REFERENCE.md` routes you to and **copy
the value out of it. Do NOT guess a geom, palette, hex, theme token, dpi, or signature
from memory.**

- **Before you organize the data** (Step 1): open `data.md` and get to **one clean,
  correctly-typed, TIDY DataFrame** — strip currency/percent strings to floats, coerce
  `object`-dtype numeric columns, parse dates to real datetimes, and **melt wide → long**
  when you have several series to plot together. plotnine maps *columns* to aesthetics,
  so an untidy frame forces manual hacks the grammar is meant to remove.
- **Before you pick the geom** (Step 2): open `geoms.md`, find the row for the user's
  *question type*, and use the geom it names — plus its knobs (bar vs col, jitter/alpha
  for overplotting, bins for histograms), its **pinned mark size** (point/line — do not
  free-associate a size), and, for a horizontal bar ranking, the mandatory tall-figure-size
  branch (exact value in `small_color.md`). Do not free-associate a chart type.
- **Before you write any color mapping** (Step 3): the exact palette name / hexes / scale
  object for your data shape live ONLY in `big_color.md`. Open it and copy them. Do not
  invent a palette or a hex, and do not color-encode more than one variable.
- **Before you set the theme** (Step 5): open `small_color.md` and run its fixed checklist
  top to bottom — base theme, panel background, gridline treatment, text sizes, legend
  position, figure size, dpi. Every neutral hex and the `save()` size/dpi are there.
- **Before you call any method you are unsure of** (any step): open `api.md` for the exact
  signature, arguments, and defaults. Do not guess an argument name.

If SKILL.md cannot answer it and you may not invent it, the reference **has** to be opened.

## Global constants (true for every plot)

Set once, never vary unless Rule 0 fires. These are **named rules**; their exact numeric
values live in the references.

- **Figure size + dpi.** Every plot saves at the house figure size and dpi (in
  `references/small_color.md`) so plots look consistent side by side. **Hard branch, not
  a suggestion:** if Step 2 chose a horizontal bar/ranking (`geom_col()`/`geom_bar()` +
  `coord_flip()`), the figure size MUST be the TALL size from `small_color.md`, never the
  landscape default — check this explicitly before Step 6, every time, don't let it
  default silently. Never ship a default-size, low-dpi render.
- **Base theme.** One house base theme applied to every plot (named in `small_color.md`).
  Do not mix themes across a session.
- **Font.** Use the theme default; do **not** set a custom font unless the user asks.
- **Mark size.** `geom_point`/`geom_line` use the pinned `point_size`/`line_size` in
  `references/geoms.md` (`pn_house_style.HOUSE_STYLE`) — never a freely chosen size.
- **Labels.** Title + both axis labels are **required** on every plot, humanized out of
  raw `snake_case`, with units where the data has them. A legend gets a real title too.
  **Title wording is templated, not free-written** — compose it from the humanized axis
  labels using the exact template for the plot's geom family in `references/geoms.md`
  (Title & label templates); do not draft a fresh sentence.
- **The house helper.** Prefer `scripts/pn_house_style.py`
  (`apply_house_style`, `house_palette`, `humanize_labels`, `save_plot`) over hand-rolling
  the theme/palette each time — same look every plot. Overridable per call (Rule 0).

## Correctness gotchas (named rules — values live in the references)

- **Tidy first.** Reshape to long form *before* building the plot; don't fight wide data
  with repeated `geom_*` layers. See `data.md`.
- **Original column names** go in `aes(...)` and `scale_*` — not humanized labels. Humanize
  only in `labs()` / the scale's `name=`.
- **Named palettes over manual lists.** When a named house palette exists for the data
  shape (`big_color.md`), use the `scale_*` for it rather than a hand-typed color list.
- **Overplotting.** Many overlapping points → alpha and/or `geom_jitter` (which MUST pin
  its `random_state` to the named `jitter_random_state` value — see `geoms.md` for the
  exact seed); a dense scatter may want `geom_bin2d`/`geom_density_2d`. `geoms.md` has
  the rule.
- **`fmt`/scales for numbers & dates.** Currency, percent, thousands need the right
  `scale_*_continuous(labels=...)`; date axes need `scale_x_date(...)` with the
  **pinned `date_breaks`/`date_labels` pair for the data's span** (`api.md` — Date-axis
  defaults) — never ship raw `1e6`-style tick labels or an eyeballed "readable ticks" guess.
- **Renderer.** End with **`p.save("plot.png", ...)`** (or `save_plot(p, "plot.png")`)
  only. plotnine renders through matplotlib in-process — no browser needed. Never call
  `plt.show()`, never fall back to writing HTML or to PIL/Pillow. If rendering fails,
  **stop and surface the error verbatim** — a fallback produces a fake plot.
- **Imports.** Import the names you use, e.g.
  `from plotnine import ggplot, aes, geom_point, geom_line, labs, theme, scale_color_manual`.
  Avoid `from plotnine import *`.
