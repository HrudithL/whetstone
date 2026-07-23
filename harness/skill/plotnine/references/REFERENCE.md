# REFERENCE.md — the router: open the right file before each decision

SKILL.md sent you here **before you write any Python**. This is a checklist you
*execute*, not an index you skim. Run it top to bottom against **your** data; for every
row that matches, open the file it names and **copy the exact value out of that file into
your code**. Do not retype a geom, palette, hex, theme token, or dpi from memory —
SKILL.md holds none of them on purpose. Filenames live here and nowhere else.

Paths below are relative to the skill's `references/` directory (this file's own
directory). The worked examples are the one exception: they live at the skill root in
`assets/` — a **sibling** of `references/` — so every example path is written with a
leading `../` (i.e. `../assets/examples/…`).

---

## 0. Unsure of any method signature / args / defaults — at any step

Open **`api.md`** and copy the exact signature. Mechanical API detail only; every design
decision stays in SKILL.md and the files below.

## 1. EVERY plot — unconditional (Steps 1, 4 & 5)

- **`data.md`** — the data-cleaning sub-step (Step 1, **before anything else**): get to
  ONE correctly-typed, **tidy (long)** DataFrame. Strip currency/percent strings to
  floats, coerce `object`-dtype numerics, parse dates, **melt wide → long** for grouped
  series, standardize missing values. plotnine maps columns to aesthetics — skip this and
  you end up hand-hacking what the grammar should do for you.
- **`small_color.md`** — the fixed Small-Color / theme checklist (base theme, panel
  background, gridlines, text sizes, legend position) plus **all neutral hexes** and the
  **house `figure_size` + `dpi` for `save()`**. Open it before Step 5 and before you save.
- **`api.md`** — the `labs()` / `scale_*` calls for the required title + axis labels and
  for number/date tick formatting (Step 4).

## 2. Choosing the form / geom (Step 2)

Open **`geoms.md`**, find the row for the user's **question type**, and use the geom it
names plus its knobs. Do not free-associate a chart type.

| The user's question is about… | Open `geoms.md` row |
|---|---|
| Relationship between two numeric variables | scatter / `geom_point` |
| Ranking or amount across categories | bar / `geom_col` / `geom_bar` |
| A trend over time / an ordered x | line / `geom_line` (+ `geom_point`) |
| The distribution of one numeric variable | histogram / density / boxplot |
| Comparing distributions across groups | boxplot / violin |
| Part-of-whole across categories | stacked / dodged bar |
| Two categoricals + a value (matrix) | `geom_tile` heatmap |

## 3. A variable will be color-encoded (Step 3 — Big Color)

**Before you write any `aes(color=...)` / `aes(fill=...)` or `scale_*`**, find your data
shape below, open **`big_color.md`**, and copy that file's palette name / hexes / scale
object. Ceiling: **≤ 1 color-encoded variable** — the hero.

| Your hero variable's shape | `big_color.md` section |
|---|---|
| **Categorical** (unordered groups) | Qualitative palette |
| **Ordered magnitude** (low→high, one direction) | Sequential palette |
| **Signed** (negative/positive, diverging around a reference) | Diverging palette |
| No variable worth color-encoding | Single house accent (no legend) |

## 4. Your data matches an archetype (Steps 2 & 5)

Open the matching worked example for a full runnable plot to pattern-match against
(`../assets/examples/EXAMPLES.md` indexes them all).

| Archetype — use when… | Open |
|---|---|
| Two numeric variables, optional grouping | `../assets/examples/scatter/` |
| Ranking / amount across categories | `../assets/examples/bar/` |
| A time trend, one or more series | `../assets/examples/line/` |
| The shape/spread of a numeric variable | `../assets/examples/distribution/` |
