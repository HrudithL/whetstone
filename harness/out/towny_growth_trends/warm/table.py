"""Population density growth trends for Ontario's fastest-growing towns.

Design follows the great-tables 7-step flowchart:
  - Step 1  ONE clean, correctly-typed DataFrame.
  - Step 2  Stub = town name; two spanners (density block + change block).
  - Step 3  Big Color = the 6-column density matrix as ONE Blues gradient
            (neutral magnitude, >=5 rows). A SINGLE neutral accent (blue),
            never green for growth (mandatory constraint I1). The signed
            percentage columns are left uncolored per that same constraint.
  - Step 4  Big Color present -> LIGHT washed-blue heading band.
  - Step 5  Small-color polish checklist.
  - Step 6  Title + subtitle + source note (states the ranking definition).
  - Step 7  .gtsave("table.png") + .as_raw_html() -> table.html.
"""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------- Step 1: data
df = pd.read_csv("towny.csv")

density_cols = [
    "density_1996", "density_2001", "density_2006",
    "density_2011", "density_2016", "density_2021",
]
change_cols = [
    "pop_change_1996_2001_pct", "pop_change_2001_2006_pct",
    "pop_change_2006_2011_pct", "pop_change_2011_2016_pct",
    "pop_change_2016_2021_pct",
]

# Canonical definition of "fastest-growing" (F-canonical-metric, stated in the
# source note): total population change from the 1996 to the 2021 census.
df["growth_1996_2021"] = (df["population_2021"] - df["population_1996"]) / df["population_1996"]

top15 = (
    df.sort_values("growth_1996_2021", ascending=False)
    .head(15)
    .loc[:, ["name", *density_cols, *change_cols]]
    .reset_index(drop=True)
)

# --------------------------------------------- Step 3 domain: ONE shared scale
lo = float(np.nanmin(top15[density_cols].to_numpy()))
hi = float(np.nanmax(top15[density_cols].to_numpy()))

year_labels = {
    "density_1996": "1996", "density_2001": "2001", "density_2006": "2006",
    "density_2011": "2011", "density_2016": "2016", "density_2021": "2021",
}
change_labels = {
    "pop_change_1996_2001_pct": "'96–'01", "pop_change_2001_2006_pct": "'01–'06",
    "pop_change_2006_2011_pct": "'06–'11", "pop_change_2011_2016_pct": "'11–'16",
    "pop_change_2016_2021_pct": "'16–'21",
}

# --------------------------------------------------------------- build the GT
gt = (
    GT(top15, rowname_col="name")
    .tab_header(
        title="Ontario's Fastest-Growing Towns",
        subtitle=md(
            "Population density (people / km²) at every census from 1996 to 2021, "
            "with period-over-period change — top 15 towns by total growth"
        ),
    )
    # Step 2 — spanners
    .tab_spanner(label="Population density (people / km²)", columns=density_cols)
    .tab_spanner(label="Period-over-period change", columns=change_cols)
    .cols_label(**year_labels, **change_labels)
    .tab_stubhead(label="Town")
    # Step 5(e) — formatting per column
    .fmt_number(columns=density_cols, decimals=1, use_seps=True)
    .fmt_percent(columns=change_cols, decimals=1, force_sign=True)  # L1: +sign
    .sub_missing(missing_text="—")
    # Step 3 — Big Color: the density matrix as ONE Blues gradient (neutral magnitude)
    .data_color(
        columns=density_cols,
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 4 — LIGHT washed-blue heading band (Big Color present)
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a) — hairline between every body row
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Step 5(c) — row striping (>=10 rows, body not fully filled)
        row_striping_background_color="#F6F6F6",
    )
    .opt_row_striping()
    # Step 5(d) — stub tint harmonized to the washed-blue Big-Color hue (grey budget)
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    .tab_style(style=style.text(weight="bold"), locations=loc.stub())
    # Step 5(b) — vertical divider at the spanner seam (last density column)
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="density_2021"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="density_2021"),
    )
    # Step 6 — source note (states the canonical ranking definition)
    .tab_source_note(
        source_note=md(
            "*Ranked by total population change from the 1996 to the 2021 census. "
            "Source: `towny` dataset, Statistics Canada census of population.*"
        )
    )
    # Global constant — the boxed Frame (all four sides)
    .tab_options(
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# ------------------------------------------------------- Step 7: render + HTML
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
print(top15[["name", "density_1996", "density_2021"]].to_string())
