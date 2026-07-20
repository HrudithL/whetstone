"""Ontario's fastest-growing towns — density trends 1996–2021 with period changes.

Built with great_tables following the skill's 7-step flowchart.
"""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------------------
# Step 1 — UNDERSTAND & CLEAN THE DATA -> one correctly-typed DataFrame
# ---------------------------------------------------------------------------
raw = pd.read_csv("towny.csv")

DENSITY = [
    "density_1996", "density_2001", "density_2006",
    "density_2011", "density_2016", "density_2021",
]
CHANGE = [
    "pop_change_1996_2001_pct", "pop_change_2001_2006_pct",
    "pop_change_2006_2011_pct", "pop_change_2011_2016_pct",
    "pop_change_2016_2021_pct",
]

# Canonical "fastest-growing" definition (F-canonical-metric, stated in source):
# total population change from the 1996 to the 2021 census, in percent.
raw["growth_1996_2021_pct"] = (
    (raw["population_2021"] - raw["population_1996"]) / raw["population_1996"]
)

top = (
    raw.sort_values("growth_1996_2021_pct", ascending=False)
    .head(15)
    .loc[:, ["name", *DENSITY, *CHANGE]]
    .reset_index(drop=True)
)

# ---------------------------------------------------------------------------
# Step 3 — BIG COLOR (<=2 colored measures)
#   1) Density block (6 yrs) = neutral magnitude matrix  -> Blues, one shared domain
#   2) Period change block (5 periods) = signed          -> RdYlGn diverging, symmetric
# ---------------------------------------------------------------------------
d_lo = float(np.nanmin(top[DENSITY].to_numpy()))
d_hi = float(np.nanmax(top[DENSITY].to_numpy()))

c_lo = float(np.nanmin(top[CHANGE].to_numpy()))
c_hi = float(np.nanmax(top[CHANGE].to_numpy()))
M = max(abs(c_lo), abs(c_hi))  # symmetric domain so 0 sits at palette midpoint

# ---------------------------------------------------------------------------
# Steps 2, 4, 5, 6 — organize, band, polish, titles (one chained expression)
# ---------------------------------------------------------------------------
gt = (
    GT(top, rowname_col="name")  # PP-13: name is the row identifier -> stub
    .tab_header(
        title="Ontario's Fastest-Growing Towns",
        subtitle=md(
            "Population **density** (residents / km²) across every census year and "
            "the period-over-period change, for the 15 municipalities with the "
            "largest total population growth from 1996 to 2021."
        ),
    )
    # --- spanners (column groups) ---
    .tab_spanner(label="Population Density  (residents / km²)", columns=DENSITY)
    .tab_spanner(label="Period-over-Period Change", columns=CHANGE)
    # --- column labels ---
    .cols_label(
        density_1996="1996", density_2001="2001", density_2006="2006",
        density_2011="2011", density_2016="2016", density_2021="2021",
        pop_change_1996_2001_pct="'96–'01",
        pop_change_2001_2006_pct="'01–'06",
        pop_change_2006_2011_pct="'06–'11",
        pop_change_2011_2016_pct="'11–'16",
        pop_change_2016_2021_pct="'16–'21",
    )
    .tab_stubhead(label="Town")
    .cols_align(align="center", columns=[*DENSITY, *CHANGE])
    # --- Step 5(e): formatting per semantic type ---
    .fmt_number(columns=DENSITY, decimals=1, use_seps=True)
    .fmt_percent(columns=CHANGE, decimals=1, force_sign=True)  # data is decimal -> default scale
    .sub_missing(missing_text="—")
    # --- Step 3: Big Color #1 — density magnitude gradient (Blues) ---
    .data_color(
        columns=DENSITY,
        palette="Blues",
        domain=[d_lo, d_hi],
        truncate=False,
        na_color="#808080",
    )
    # --- Step 3: Big Color #2 — signed change, diverging (RdYlGn, positive = growth = green) ---
    .data_color(
        columns=CHANGE,
        palette="RdYlGn",
        domain=[-M, M],
        truncate=False,
        na_color="#808080",
    )
    # --- Step 4: LIGHT heading band (Big Color present) -> washed Blues tint ---
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): cell hairlines
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame: boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # Step 5(d): stub tint -> washed Blues tint (harmonized, grey-budget rule)
    .tab_style(
        style=style.fill(color="#EAF0F6"),
        locations=loc.stub(),
    )
    .tab_style(
        style=style.text(weight="bold"),
        locations=loc.stub(),
    )
    # Step 5(b): vertical divider at the group boundary (body + header)
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=[
            loc.body(columns="density_2021"),
            loc.column_labels(columns="density_2021"),
        ],
    )
    # Step 6: source notes (metric definition + reading guide)
    .tab_source_note(
        source_note=md(
            "**Ranking:** *fastest-growing* = largest total population change from the "
            "1996 to the 2021 census. **Change columns:** period-over-period population "
            "growth (green = gain, red = decline; density shares the same rate as land "
            "area is fixed)."
        )
    )
    .tab_source_note(
        source_note=md("Source: Towny — Ontario census municipalities, 1996–2021.")
    )
    .tab_options(table_font_size="13px")
)

# ---------------------------------------------------------------------------
# Step 7 — RENDER (mandatory) + self-contained HTML
# ---------------------------------------------------------------------------
gt.gtsave("table.png", expand=15, vwidth=1500)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
