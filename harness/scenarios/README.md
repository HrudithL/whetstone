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
`airquality_monthly_summary`, `gtcars_top10_by_country`, `towny_growth_trends`,
`sp500_monthly_performance`.

## Choosing `polarity: learning` vs. `polarity: issue`

This is decided by **how the correction is phrased**, not by how big or structural the change is.
A preference is `issue` only when it reads as a standing, always/never house rule the user is
stating for every future task in this scope — e.g. `towny_growth_trends.yaml`'s `density-magenta`
("Never fill growth with green here (house rule)") or `pricing_cards.yaml`'s `sharp-corners`
("Never round any corner"). Everything else — including a real data-shape/layout/slide-order
restructuring that is a one-off correction to *this* task, not an eternal rule — is `learning`.
Reaching for `issue` because a preference is a big or structural change (rather than a cosmetic
tweak) mislabels a subjective, one-off correction as an objective, mandatory, permanent rule; the
showcase's `polarity` column is read directly by site visitors (see `docs/methodology.qmd`), so a
mislabeled entry there is not just an internal inconsistency.
