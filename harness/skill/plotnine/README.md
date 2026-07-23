# Vendored plotnine skill

A copy of the sibling `plotnineskill` repo's `plotnine` Claude skill, mounted by the runner's
`--agent` (live) generator so the showcase is self-contained. Example **PNG** assets were dropped to
keep it light — the `.py` examples under `assets/examples/`, `EXAMPLES.md`, and all reference text
are intact. Regenerate/refresh from `../../../plotnineskill/.claude/skills/plotnine/`.

## Deviation from source

**None.** Unlike the vendored `great-tables` skill (whose upstream `gt.gtsave(...)` needed a
module-level shim and was corrected to the instance method here), plotnine's mandated renderer
`p.save("plot.png", ...)` is a genuine `ggplot`-instance method that works as written with an
unmodified `plotnine` install — so SKILL.md and the `references/` are copied verbatim. The runner's
prompt tail instructs writing `plot.py` ending in `p.save("plot.png", ...)`; the live run fails if
`plot.py` is produced without a non-empty `plot.png`.
