"""Clean GT-cars table: model, horsepower, and price.

Built with great_tables following the skill's 7-step flowchart:
  1. Data      : one row per car; model = identifier (stub), hp + msrp = measures.
  2. Columns   : show model (stub), hp, msrp; sorted by price so the heat-map flows.
  3. Big Color : two ordered magnitudes qualify -> both colored (<=2 ceiling).
                 hp   -> Blues  (primary neutral magnitude).
                 msrp -> YlOrBr (warm heat-map, per user preference).
  4. Band      : Big Color present -> LIGHT grey band.
  5. Small clr : hairlines, warm washed stub tint (grey-budget), fmt per type, frame.
  6. Titles    : title + subtitle + source note.
  7. Render    : .gtsave("table.png") + .as_raw_html() -> table.html
"""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# --- Step 1: one clean, correctly-typed DataFrame -------------------------------
df = pd.read_csv("gtcars.csv")
# hp and msrp already parse as floats; select and sort by price (desc) so the
# warm price heat-map reads top-to-bottom.
df = (
    df[["model", "hp", "msrp"]]
    .sort_values("msrp", ascending=False)
    .reset_index(drop=True)
)

# --- Step 3: data-driven domains for each colored measure -----------------------
hp_lo, hp_hi = float(np.nanmin(df["hp"])), float(np.nanmax(df["hp"]))
msrp_lo, msrp_hi = float(np.nanmin(df["msrp"])), float(np.nanmax(df["msrp"]))

gt = (
    GT(df, rowname_col="model")
    # ---- Step 6: titles + source ----
    .tab_header(
        title=md("**The GT Cars Collection**"),
        subtitle="Horsepower and manufacturer's suggested retail price, by model",
    )
    .tab_source_note(
        source_note=md("Source: the *gtcars* dataset. Prices are U.S. MSRP.")
    )
    # ---- Step 5(e): formatting per column ----
    .fmt_number(columns="hp", decimals=0, use_seps=True)
    .fmt_currency(columns="msrp", decimals=0, use_seps=True)
    .sub_missing(missing_text="—")
    .cols_label(hp="Horsepower", msrp="Price")
    .cols_align(align="right", columns=["hp", "msrp"])
    # ---- Step 3: Big Color (two neutral magnitudes) ----
    .data_color(
        columns="hp",
        palette="Blues",
        domain=[hp_lo, hp_hi],
        truncate=False,
        na_color="#808080",
    )
    .data_color(
        columns="msrp",
        palette="YlOrBr",
        domain=[msrp_lo, msrp_hi],
        truncate=False,
        na_color="#808080",
    )
    # ---- Step 5(d): stub tint (warm washed Ochre, echoing the YlOrBr heat-map) ----
    .tab_style(
        style=style.fill(color="#F5EFDC"),
        locations=loc.stub(),
    )
    # ---- Step 4: LIGHT heading band + Step 5(a) borders ----
    .tab_options(
        # light band (Big Color present)
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # hairlines between rows
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame: boxed light border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# --- Step 7: render the mandatory PNG + the embeddable HTML ----------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as fh:
    fh.write(gt.as_raw_html())

print("Wrote table.png and table.html")
