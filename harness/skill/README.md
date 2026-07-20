# Vendored great-tables skill

A copy of the sibling `gtskill` repo's `great-tables` Claude skill, mounted by the runner's
`--agent` (live) generator so the showcase is self-contained. Example **PNG** assets were dropped
to keep it light — the `.py` examples and all reference text are intact. Regenerate/refresh from
`../gtskill/.claude/skills/great-tables/`.

## Deviation from source

The upstream `gtskill` skill instructs the renderer as a **module-level** `gt.gtsave(...)` call, which
works there only via that repo's `gtskill_sidecar.py` shim. `great_tables` exposes no module-level
`gtsave` — only the `GT` instance methods `.gtsave()` / `.save()`. Since this vendored copy is mounted
**without** the sidecar, every module-level `gt.gtsave(...)` mention across `SKILL.md` and the
`references/` (`api.md`, `small_color.md`) was corrected to the **instance method** call
`.gtsave(...)` (on the constructed `GT` object), and the runner's prompt likewise instructs
`table.gtsave("table.png")`. The renderer bullet was also updated to **additionally** write the
table's HTML via `.as_raw_html()` to `table.html` (the site embeds it natively): the upstream skill
*forbade* writing `table.html`, treating it as a screenshot substitute — here it is an *extra*
artifact, not a replacement for the real PNG render. The runner fails a live run that produces
`table.py` but no non-empty `table.png` **and** `table.html`.
