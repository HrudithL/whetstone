"""GT cars — horsepower and price, rolled up to one row per manufacturer.

Flowchart trace (great-tables skill):
  1 UNDERSTAND  47 raw model rows; grain = model. Roll up with a real groupby to
                one row per `mfr`: mean hp, mean msrp, and a model count so the
                reader can tell a 2-model average from a 12-model one.
                hp/msrp are already float64 in the CSV; no NAs in either.
  2 ORGANIZE    stub = mfr (PP-13 identifier trigger). Spanner "Lineup Average"
                over the two mean measures; Models sits outside it.
                Canonical metric (PP-18): unweighted mean over the models the
                dataset lists — stated in the subtitle + source note.
  3 BIG COLOR   two ordered magnitudes over 19 rows -> both qualify for gradient
                fill (>=5 rows). Prompt names horsepower first => primary = hp
                (Blues); secondary neutral takes the next rung of the pinned
                Blues -> Greens ladder => msrp (Greens). Models stays uncolored
                (the <=2 ceiling). Domains are data-driven, truncate=False.
  4 BAND        Big Color present => LIGHT band (grey #F0F0F0), 2px #CCCCCC rule.
  5 SMALL COLOR hairlines; group divider right of Models; striping (19 rows, body
                not fully filled); stub tinted #EAF0F6 (grey-budget: band +
                stripes + stub grey with Blues fills -> recolor the stub, the
                highest-priority element, to the washed-Navy tint); fmt_* per
                semantic type; square four-side frame.
  6 TITLES      title + subtitle, stacked source notes.
  7 RENDER      .gtsave("table.png", expand=15) + .as_raw_html() -> table.html
"""

import numpy as np
import pandas as pd
from great_tables import GT, loc, style

# --- Step 1: load + clean -------------------------------------------------
cars = pd.read_csv("gtcars.csv")
cars["mfr"] = cars["mfr"].str.strip()
cars["hp"] = pd.to_numeric(cars["hp"], errors="coerce")
cars["msrp"] = pd.to_numeric(cars["msrp"], errors="coerce")

# Roll up the raw model rows to one row per manufacturer (real groupby agg).
by_mfr = (
    cars.groupby("mfr")
    .agg(models=("model", "count"), hp=("hp", "mean"), msrp=("msrp", "mean"))
    .reset_index()
    .sort_values("hp", ascending=False)
    .reset_index(drop=True)
)

# --- Step 3: data-driven domains, one per colored measure -----------------
hp_lo = float(np.nanmin(by_mfr[["hp"]].to_numpy()))
hp_hi = float(np.nanmax(by_mfr[["hp"]].to_numpy()))
msrp_lo = float(np.nanmin(by_mfr[["msrp"]].to_numpy()))
msrp_hi = float(np.nanmax(by_mfr[["msrp"]].to_numpy()))

n_models = int(by_mfr["models"].sum())
n_mfr = len(by_mfr)

table = (
    GT(by_mfr, rowname_col="mfr")
    .tab_header(
        title="Horsepower and Price Across the GT Car Marques",
        subtitle=(
            f"Lineup averages for {n_mfr} manufacturers, built from all "
            f"{n_models} model rows in the gtcars set"
        ),
    )
    .tab_stubhead(label="Manufacturer")
    .tab_spanner(label="Lineup Average", columns=["hp", "msrp"])
    .cols_label(models="Models", hp="Horsepower", msrp="Price (MSRP)")
    # --- Step 5(e): fmt_* per semantic type ---
    .fmt_integer(columns="models")
    .fmt_number(columns="hp", decimals=0, use_seps=True)
    .fmt_currency(columns="msrp", currency="USD", decimals=0, use_seps=True)
    .sub_missing(columns=["models", "hp", "msrp"], missing_text="—")
    .cols_align(align="right", columns=["models", "hp", "msrp"])
    .cols_width(mfr="190px", models="100px", hp="150px", msrp="170px")
    # --- Step 3: Big Color, two colored measures ---
    .data_color(
        columns=["hp"],
        palette="Blues",
        domain=[hp_lo, hp_hi],
        truncate=False,
        na_color="#808080",
    )
    .data_color(
        columns=["msrp"],
        palette="Greens",
        domain=[msrp_lo, msrp_hi],
        truncate=False,
        na_color="#808080",
    )
    # --- Step 5(c): striping ---
    .opt_row_striping()
    # --- Step 5(d) + grey budget: washed-Navy stub tint ---
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    # --- Step 5(b): column-group divider at the one group boundary ---
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="models"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="models"),
    )
    # --- Step 6: stacked footer notes ---
    .tab_source_note(
        source_note=(
            "Averages are unweighted means of the models each manufacturer lists "
            "in the dataset; the Models column gives the number of rows behind "
            "each average."
        )
    )
    .tab_source_note(
        source_note="Source: gtcars dataset (Posit / great_tables sample data)."
    )
    .tab_options(
        # Step 5(a): hairlines + the Step-4 column-label bottom rule
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 4: LIGHT band (Big Color present), dark bold labels
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        row_striping_background_color="#F6F6F6",
        # Frame: square light border on all four sides
        table_border_top_style="solid",
        table_border_top_color="#CCCCCC",
        table_border_top_width="1px",
        table_border_bottom_style="solid",
        table_border_bottom_color="#CCCCCC",
        table_border_bottom_width="1px",
        table_border_left_style="solid",
        table_border_left_color="#CCCCCC",
        table_border_left_width="1px",
        table_border_right_style="solid",
        table_border_right_color="#CCCCCC",
        table_border_right_width="1px",
    )
)

# --- Step 7: render (mandatory renderer) + native HTML artifact -----------
table.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(table.as_raw_html())

print(f"Wrote table.png and table.html — {n_mfr} manufacturers, {n_models} models.")
