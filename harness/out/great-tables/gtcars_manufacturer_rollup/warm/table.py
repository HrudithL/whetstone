"""Build a manufacturer-level rollup of the GT cars, showing mean horsepower and
mean price across each manufacturer's whole lineup, rendered with great_tables."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------- Step 1: DATA
# Raw grain is one row per car model. Roll up to one row per manufacturer with a
# real groupby aggregation over the raw rows (mean hp, mean msrp), plus a count
# of models so the average is interpretable.
raw = pd.read_csv("gtcars.csv")

df = (
    raw.groupby("mfr", as_index=False)
    .agg(
        models=("model", "size"),
        hp=("hp", "mean"),
        msrp=("msrp", "mean"),
    )
    .sort_values("hp", ascending=False)
    .reset_index(drop=True)
)

# ------------------------------------------------- Step 3: BIG COLOR domains
# Two neutral magnitudes (horsepower + price) → both qualify as colored measures
# (19 rows ≥ 5). Prompt names horsepower first → primary = Blues; secondary
# price → Greens (neutral tie-breaker ladder Blues → Greens).
hp_lo = float(np.nanmin(df[["hp"]].to_numpy()))
hp_hi = float(np.nanmax(df[["hp"]].to_numpy()))
msrp_lo = float(np.nanmin(df[["msrp"]].to_numpy()))
msrp_hi = float(np.nanmax(df[["msrp"]].to_numpy()))

BAND = "#EAF0F6"  # washed-Blues tint (dominant Big-Color hue) for band + stub

gt = (
    GT(df, rowname_col="mfr")
    # -------------------------------------------------- Step 2: organize columns
    .tab_spanner(label="Lineup Averages", columns=["hp", "msrp"])
    .cols_label(
        models="Models",
        hp="Avg. Horsepower",
        msrp="Avg. Price",
    )
    .tab_stubhead(label="Manufacturer")
    .cols_align(align="center", columns=["models"])
    # ------------------------------------------------------ Step 5(e): formatting
    .fmt_number(columns=["hp", "models"], decimals=0, use_seps=True)
    .fmt_currency(columns="msrp", decimals=0, use_seps=True)
    # ------------------------------------------------------- Step 3: Big Color
    .data_color(
        columns="hp",
        palette="Blues",
        domain=[hp_lo, hp_hi],
        truncate=False,
        na_color="#808080",
    )
    .data_color(
        columns="msrp",
        palette="Greens",
        domain=[msrp_lo, msrp_hi],
        truncate=False,
        na_color="#808080",
    )
    # ---------------------------------------------- Step 6: titles & annotations
    .tab_header(
        title="GT Cars — Horsepower & Price by Manufacturer",
        subtitle="Mean horsepower and MSRP across each manufacturer's full GT lineup",
    )
    .tab_source_note(source_note=md("Source: the **gtcars** dataset (2014–2017 model years)."))
    .tab_source_note(
        source_note="Averages computed over all models per manufacturer; ordered by mean horsepower."
    )
    # ---------------------------------------------------- Step 4: LIGHT band
    .tab_options(
        column_labels_background_color=BAND,
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): cell hairlines
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame — boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # ------------------------------------------------------- Step 5(d): stub tint
    .tab_style(style=style.fill(color=BAND), locations=loc.stub())
    .tab_style(style=style.text(weight="bold"), locations=loc.stub())
    # ------------------------------------ Step 5(b): column-group vertical divider
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="models"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="models"),
    )
)

gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("wrote table.png and table.html")
print(df.to_string())
