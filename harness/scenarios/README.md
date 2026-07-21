# Scenarios

One `*.yaml` file per showcase scenario. Each pairs a great-tables task (from the sibling `gtskill`
corpus) with the subjective preference(s) we expect the learned layer to capture and re-apply. The
schema and a full annotated example live in [`../schema.py`](../schema.py); `load_scenario` /
`load_scenarios` there validate every file and error on a missing or invalid field.

Scenarios are **authored in slice 2** (`feat/m3-scenarios`) — the six gtskill prompts:
`gtcars_hp_price`, `islands_sizes`, `airquality_monthly_summary`, `gtcars_top10_by_country`,
`towny_growth_trends`, `sp500_monthly_performance`.
