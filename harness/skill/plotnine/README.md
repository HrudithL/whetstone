# Vendored plotnine skill

A copy of the sibling `plotnineskill` repo's `plotnine` Claude skill, mounted by the runner's
`--agent` (live) generator so the showcase is self-contained. Example **PNG** assets were dropped to
keep it light — the `.py` examples under `assets/examples/`, `EXAMPLES.md`, and all reference text
are intact. Regenerate/refresh from `../../../plotnineskill/.claude/skills/plotnine/`.

## Deviation from source

Unlike the vendored `great-tables` skill (whose upstream `gt.gtsave(...)` needed a
module-level shim and was corrected to the instance method here), plotnine's mandated renderer
`p.save("plot.png", ...)` is a genuine `ggplot`-instance method that works as written with an
unmodified `plotnine` install — so no shim was ever needed. The runner's prompt tail instructs
writing `plot.py` ending in `p.save("plot.png", ...)`; the live run fails if `plot.py` is produced
without a non-empty `plot.png`.

**M6a determinism fix.** The skill originally pinned zero `geom_point`/`geom_line` mark size, had
no title-wording template, no date-axis breaks default (just "readable ticks" prose), only
reference-file prose (not a hard rule) for the tall-bar-ranking `(6,7)` figure size, and no seed
requirement for `geom_jitter`. Those gaps let the skill's own *unlearned* baseline vary run to run,
independent of any taught preference — undermining the cold-vs-warm showcase diff. This copy now
pins `point_size`/`line_size`/`jitter_random_state` in `scripts/pn_house_style.py`
(`HOUSE_STYLE`), a title-template table and a `geom_jitter` seed rule in `references/geoms.md`, a
date-axis breaks/labels-by-span table in `references/api.md`, and a hard `(6,7)` figure-size branch
in `SKILL.md` itself (previously only in `references/small_color.md` prose). If refreshing from
`../../../plotnineskill/.claude/skills/plotnine/`, reapply these on top unless upstream has adopted
them too.
