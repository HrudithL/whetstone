# Vendored great-tables skill

A copy of the sibling `gtskill` repo's `great-tables` Claude skill, mounted by the runner's
`--agent` (live) generator so the showcase is self-contained. Example **PNG** assets were dropped
to keep it light — the `.py` examples and all reference text are intact. Regenerate/refresh from
`../gtskill/.claude/skills/great-tables/`.

## Deviation from source

The upstream `gtskill` skill instructs the renderer as module-level `gt.gtsave("table.png")`, which
works there only via that repo's `gtskill_sidecar.py` shim. `great_tables` exposes no module-level
`gtsave` — only the `GT` instance methods `.gtsave()` / `.save()`. Since this vendored copy is mounted
**without** the sidecar, the three renderer mentions in `SKILL.md` were corrected to the instance
method `GT.gtsave("table.png")`, and the runner's prompt likewise instructs `table.gtsave("table.png")`.
The runner additionally fails a live run that produces `table.py` but no rendered `table.png`.
