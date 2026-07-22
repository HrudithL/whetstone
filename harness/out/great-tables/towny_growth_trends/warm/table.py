"""Population-density growth for the 15 fastest-growing Ontario towns (1996–2021)."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------- Step 1: data
df = pd.read_csv("towny.csv")

DENS = ["density_1996", "density_2001", "density_2006",
        "density_2011", "density_2016", "density_2021"]
PCT = ["pop_change_1996_2001_pct", "pop_change_2001_2006_pct",
       "pop_change_2006_2011_pct", "pop_change_2011_2016_pct",
       "pop_change_2016_2021_pct"]

# A town can only fulfil "the percentage change between each period" if it has a
# complete run of census period-change data — drop the few rows that don't.
df = df.dropna(subset=PCT).copy()

# "Fastest-growing" = largest total density growth over the full 1996–2021 window.
df["_growth"] = df["density_2021"] / df["density_1996"] - 1
top = (df.sort_values("_growth", ascending=False)
         .head(15)
         .loc[:, ["name", *DENS, *PCT]]
         .reset_index(drop=True))

# ------------------------------------------------------- Step 3: Big Color domain
# ONE shared domain across all six density facet columns (data-driven).
lo = float(np.nanmin(top[DENS].to_numpy()))
hi = float(np.nanmax(top[DENS].to_numpy()))

# ------------------------------------------------------------- Build the table
gt = (
    GT(top, rowname_col="name")
    .tab_header(
        title="Ontario's Fastest-Growing Towns by Population Density",
        subtitle=md(
            "Residents per km² across the census years **1996–2021**, with the "
            "percent change between each period — the 15 towns with the largest "
            "density growth from 1996 to 2021"
        ),
    )
    .tab_spanner(label="Population density (residents / km²)", columns=DENS)
    .tab_spanner(label="Change between census periods", columns=PCT)
    .cols_label(
        density_1996="1996", density_2001="2001", density_2006="2006",
        density_2011="2011", density_2016="2016", density_2021="2021",
        pop_change_1996_2001_pct="’96→’01",
        pop_change_2001_2006_pct="’01→’06",
        pop_change_2006_2011_pct="’06→’11",
        pop_change_2011_2016_pct="’11→’16",
        pop_change_2016_2021_pct="’16→’21",
    )
    # ----------------------------------------------- Step 5(e): formatting
    .fmt_number(columns=DENS, decimals=1, use_seps=True)
    .fmt_percent(columns=PCT, decimals=1, force_sign=True)  # +sign on positives (L1)
    .sub_missing(missing_text="—")
    # ------------------------------------------------ Step 3: PuRd heat-map (I1)
    .data_color(
        columns=DENS,
        palette="PuRd",          # house rule: magenta ramp, never green for growth
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # ------------------------------------------------- Step 5(b): group divider
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="density_2021"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="density_2021"),
    )
    # ------------------------------------ Step 5(d): stub tint (washed magenta)
    # Grey-budget: band + stripes + hairlines already grey → lift the stub to a
    # pale PuRd tint so the quiet chrome echoes the magenta heat-map.
    .tab_style(style=style.fill(color="#F3E8F1"), locations=loc.stub())
    # -------------------------------------------------- Step 5(c): row striping
    .opt_row_striping()
    # ------------------------------------------ Step 6: caption / source note
    .tab_source_note(
        md("Source: the **towny** dataset (Statistics Canada census populations, "
           "1996–2021). Density = census population ÷ land area (km²).")
    )
    # ------------------------ Step 4 band (light) + Step 5(a) borders + Frame
    .tab_options(
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        row_striping_background_color="#F6F6F6",
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# ------------------------------------------------------- Step 7: render + embed
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print(f"Rendered {len(top)} towns | density domain [{lo:.2f}, {hi:.2f}]")
