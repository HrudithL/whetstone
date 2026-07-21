"""Population-density growth for Ontario's 15 fastest-growing towns (1996–2021).

Built with great_tables following the skill's 7-step flowchart:
  Big Color = TWO colored measures (the ceiling):
    1. Population density across the six census years -> sequential heatmap
       (neutral magnitude -> Blues), one shared domain across all year columns.
    2. Percent change between successive census periods -> diverging fill
       (signed, positive = growth = good -> RdYlGn), symmetric domain about 0.
  Heading band -> LIGHT (Big Color present), washed-Navy tint matching the Blues
  heatmap. Small-Color polish per the fixed checklist.
"""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------- Step 1: data
raw = pd.read_csv("towny.csv")

DENS = ["density_1996", "density_2001", "density_2006",
        "density_2011", "density_2016", "density_2021"]
CHG = ["pop_change_1996_2001_pct", "pop_change_2001_2006_pct",
       "pop_change_2006_2011_pct", "pop_change_2011_2016_pct",
       "pop_change_2016_2021_pct"]

# Canonical definition of "fastest-growing" (F-canonical-metric, stated in the
# source note): highest total percentage population growth 1996 -> 2021, among
# municipalities with a meaningful base (>= 1,000 residents in 1996) so that
# tiny-population statistical artifacts (e.g. 2 -> 16 residents) are excluded.
# Land area is fixed per municipality, so density change % == population change %.
base = raw[raw["population_1996"] >= 1000].copy()
base["total_growth"] = (
    base["population_2021"] - base["population_1996"]) / base["population_1996"]

top = (base.sort_values("total_growth", ascending=False)
           .head(15)
           .reset_index(drop=True))

df = top[["name"] + DENS + CHG].copy()

# ---------------------------------------------- data-driven color domains
dlo = float(np.nanmin(df[DENS].to_numpy()))
dhi = float(np.nanmax(df[DENS].to_numpy()))                 # heatmap: [min, max]

clo = float(np.nanmin(df[CHG].to_numpy()))
chi = float(np.nanmax(df[CHG].to_numpy()))
M = max(abs(clo), abs(chi))                                 # diverging: [-M, M]

# ------------------------------------------------------------- Step 2-6: build
gt = (
    GT(df, rowname_col="name")
    .tab_header(
        title="Ontario's Fastest-Growing Towns Are Getting Denser",
        subtitle=md(
            "Population density (residents per km²) across the census years "
            "**1996–2021**, with the percent change between each period"),
    )
    .tab_stubhead(label="Town")
    # ---- spanners (column groups) ----
    .tab_spanner(label="Population density (residents / km²)", columns=DENS)
    .tab_spanner(label="Change between census periods", columns=CHG)
    .cols_label(
        density_1996="1996", density_2001="2001", density_2006="2006",
        density_2011="2011", density_2016="2016", density_2021="2021",
        pop_change_1996_2001_pct="’96–’01",
        pop_change_2001_2006_pct="’01–’06",
        pop_change_2006_2011_pct="’06–’11",
        pop_change_2011_2016_pct="’11–’16",
        pop_change_2016_2021_pct="’16–’21",
    )
    # ---- Step 5(e): formatting per column ----
    .fmt_number(columns=DENS, decimals=1, use_seps=True)
    .fmt_percent(columns=CHG, decimals=1, force_sign=True)
    .sub_missing(columns=DENS + CHG, missing_text="—")
    # ---- Step 3: Big Color measure 1 — density heatmap (Blues, neutral magnitude) ----
    .data_color(
        columns=DENS,
        palette="Blues",
        domain=[dlo, dhi],
        truncate=False,
        na_color="#808080",
    )
    # ---- Step 3: Big Color measure 2 — period change, diverging (RdYlGn, +=growth) ----
    .data_color(
        columns=CHG,
        palette="RdYlGn",
        reverse=False,
        domain=[-M, M],
        truncate=False,
        na_color="#808080",
    )
    # ---- Step 4: LIGHT heading band (washed-Navy tint of the Blues heatmap) ----
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): cell hairlines between rows
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame: boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # ---- Step 5(d): stub tint (washed-Navy, harmonized with the band) ----
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    .tab_style(style=style.text(weight="bold"), locations=loc.stub())
    # ---- Step 5(b): vertical divider at the group boundary ----
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="density_2021"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="density_2021"),
    )
    # ---- Step 6: source notes ----
    .tab_source_note(
        source_note=md(
            "**Ranking:** the 15 municipalities with the highest total population "
            "growth from 1996 to 2021 (limited to those with ≥ 1,000 residents in "
            "1996 to exclude tiny-base statistical outliers). Because each "
            "municipality's land area is fixed, density change equals population "
            "change over every period."))
    .tab_source_note(
        source_note=md(
            "Blue shading encodes density (darker = denser); red–green shading "
            "encodes period growth (green = gain, red = decline)."))
    .tab_source_note(source_note="Source: towny — Statistics Canada Census of Population, 1996–2021.")
    .cols_align(align="right", columns=DENS + CHG)
)

gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
