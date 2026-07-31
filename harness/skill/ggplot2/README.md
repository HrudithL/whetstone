# Vendored ggplot2 skill

A compact skill for building plots in R with **ggplot2** (the grammar of graphics), vendored so the
showcase harness is self-contained. Mounted by the runner's `--agent` (live) generator for
`skill: ggplot2` scenarios.

## Why this skill exists

Every other showcase skill (`great-tables`, `frontend-design`, `pptx`, `plotnine`) generates Python.
Whetstone itself is language- and skill-agnostic — the learned layer is plain prose, not code — but
nothing in the showcase demonstrated that until now. `ggplot2` is the direct R analog of the
`plotnine` skill (same "visual/formatted output" class, same grammar-of-graphics idiom), so the
showcase can show the identical mechanism working on an R plotting skill, not just Python ones.

## Scope

Deliberately lean (pptx-sized, not plotnine's full reference-file tree): a plan → build → save
workflow with a short defaults checklist and a **Rule 0** making the learned layer override
stylistic defaults — the hook the showcase relies on. The COLD run builds a reasonable plot that
doesn't happen to honor the scenario's arbitrary preference; the WARM run applies the recalled
preference (a palette, a theme, a legend position, ...) once it's been taught.

The runner asks the model to write **`plot.R`** and run it with `Rscript plot.R` to produce
**`plot.png`** — see this skill's `SkillSpec` in [`../../skills.py`](../../skills.py). Because the
output is R source, preferences are checked against R text with a `#`-comment stripper
(`check_language: "r"`, `harness/generate.py`'s `_r_for_check`) — R has no block comments or
docstrings, so a quote-aware line-comment strip is enough.

**Requires R + `ggplot2`/`tidyverse` installed and on `PATH`** for a live `--agent` run (R isn't
pip-installable, so unlike the Python skills there's no venv-pinned dependency — this is a
maintainer-run, not a CI-run, step; see `harness/README.md`).
