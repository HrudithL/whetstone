# Scenarios

One `*.yaml` file per showcase scenario. Each pairs a task for one **skill** (`skill:` —
`great-tables`, `frontend-design`, `pptx`, ...) with the subjective preference(s) we expect the
learned layer to capture and re-apply. The `skill` selects a `SkillSpec` (see
[`../skills.py`](../skills.py): primary output artifact, check language, generation prompt) and the
vendored skill dir under [`../skill/`](../skill/) that the `--agent` runner mounts. The schema and a
full annotated example live in [`../schema.py`](../schema.py); `load_scenario` / `load_scenarios`
validate every file and error on a missing or invalid field. Scenario `name`s are unique across
**all** files (independent of skill) — a name is the `out/<skill>/<name>/` leaf and half the store id.

The original six (skill `great-tables`, from the sibling `gtskill` corpus): `gtcars_hp_price`,
`islands_sizes`, `airquality_monthly_summary`, `gtcars_top10_by_country`, `towny_growth_trends`,
`sp500_monthly_performance`.
