# Worked examples

Each folder has a runnable `<name>.py` and its rendered `<name>.png`. They are the
canonical pattern for their archetype — every one follows the 6-step flowchart, uses the
`pn_house_style` helpers, and ends with `save_plot(...)`. Pattern-match against the
closest one; copy its structure, not its literal columns.

| Archetype | Folder | Geom | Big Color |
|---|---|---|---|
| Relationship, two numeric vars + grouping | `scatter/` | `geom_point` (+ `geom_smooth`) | qualitative (categorical hero) |
| Ranking / amount across categories | `bar/` | `geom_col` + `coord_flip` | none → single house accent, no legend |
| Trend over time, single series | `line/` | `geom_line` | none → single house accent, no legend |
| Compare distributions across groups | `distribution/` | `geom_boxplot` | qualitative (group hero) |

Run any of them from the repo root:
```bash
.venv/bin/python .claude/skills/plotnine/assets/examples/scatter/scatter.py
```
