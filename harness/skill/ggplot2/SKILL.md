---
name: ggplot2
description: Use when the user's request involves building any plot, chart, or data visualization with `ggplot2`, `ggplot`, the grammar of graphics in R, or turning tabular data (CSV, data frame, spreadsheet) into a rendered plot PNG. Generates an R script using ggplot2 that lays out one clear, publication-ready plot and saves it with `ggsave()`. Invoke before writing any R: the plot plan (geom, palette, theme) shapes the whole script.
---

# ggplot2 (R plots)

Build plots in R with **ggplot2** (the grammar of graphics). Produce one plot that reads as a
single, finished product: one clear geom for the question being asked, a small deliberate palette,
and a consistent theme.

## Workflow

1. **Plan the plot** from the request: what question is being asked of the data (relationship,
   ranking, trend, distribution, part-of-whole), which column(s) answer it, and whether a variable
   needs to be color-encoded.
2. **Build it** with `ggplot2`:
   - `library(ggplot2)` (and `readr`/`dplyr` as needed to load and tidy the data).
   - Map the question to one geom: relationship → `geom_point()`; trend → `geom_line()`; ranking or
     amount → `geom_col()`/`geom_bar()`; distribution → `geom_histogram()`/`geom_density()`/
     `geom_boxplot()`.
   - Add real axis labels and a title with `labs(...)` — humanized, with units where the data has
     them, never the raw column name.
   - Style deliberately: a `scale_*` for any color-encoded variable, a `theme_*()` base, and
     `theme(...)` overrides (legend position, text sizes) where the design calls for them.
3. **Save and verify**: `ggsave("plot.png", plot, width = ..., height = ..., dpi = ...)`, then run
   the script (`Rscript plot.R`) so the PNG is actually produced.

## Defaults (used only absent an instruction)

- Base theme `theme_minimal()`.
- A single muted blue accent (`"#2C6FB3"`) when no variable is color-encoded; a qualitative
  ColorBrewer palette (`scale_color_brewer()`/`scale_fill_brewer()`) when one is.
- Legend on the right, when a legend is needed at all.
- A moderate point/line size — ggplot2's own defaults; don't free-associate a size.
- `ggsave(..., width = 8, height = 5, dpi = 150)`.

## Rule 0 — the user's instructions override every default

Every default above is just a default. Any explicit instruction in the prompt or the learned layer
(a specific palette, theme, legend position, point size, axis scale) **wins** — apply it exactly and
drop the conflicting default silently. The defaults decide what to do only *in the absence of* an
instruction; they never override one.
