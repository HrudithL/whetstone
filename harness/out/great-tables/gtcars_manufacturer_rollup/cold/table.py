"""GT cars — horsepower and price.

Built with the great-tables skill flowchart:
  1 UNDERSTAND   47 cars, grain = one car (mfr + model); measures = hp, msrp (both clean floats)
  2 ORGANIZE     stub = car (PP-13 identifier trigger); rows sorted by hp desc; no grouping
                 (mfr = 19 levels over 47 rows -> not a low-cardinality organizing story)
  3 BIG COLOR    two neutral magnitudes, >=5 rows -> both colored (ceiling is 2):
                 hp (prompt-named first, primary) = Blues; msrp (secondary) = Greens
                 per the neutral tie-breaker ladder Blues -> Greens -> Oranges
  4 BAND         Big Color present -> LIGHT band, washed tint of the dominant hue (Blues) #EAF0F6
  5 SMALL COLOR  hairlines, striping (>=10 rows), stub tint (grey-budget -> washed blue), fmt_*
  6 TITLES       title + subtitle, stacked footer notes (caption + source)
  7 RENDER       .gtsave("table.png") + .as_raw_html() -> table.html
"""

import numpy as np
import pandas as pd
from great_tables import GT, loc, style

# ---------------------------------------------------------------- Step 1: data
df = pd.read_csv("gtcars.csv")

# hp and msrp already import as float64 — no currency/percent strings to strip.
# Trim whitespace in the string keys that build the row label.
df["mfr"] = df["mfr"].str.strip()
df["model"] = df["model"].str.strip()

# One human-readable label per row; two columns would force the reader to
# mentally join mfr + model on every line.
df["car"] = df["mfr"] + " " + df["model"]

# ------------------------------------------------------------ Step 2: organize
# Sort by horsepower descending: the ordering is what makes the gradient readable.
tbl = (
    df.sort_values("hp", ascending=False)
    .reset_index(drop=True)[["car", "year", "hp", "msrp"]]
)

# ----------------------------------------------------------- Step 3: Big Color
# Data-driven domains, one per measure (never a round guess).
hp_lo = float(np.nanmin(tbl[["hp"]].to_numpy()))
hp_hi = float(np.nanmax(tbl[["hp"]].to_numpy()))
msrp_lo = float(np.nanmin(tbl[["msrp"]].to_numpy()))
msrp_hi = float(np.nanmax(tbl[["msrp"]].to_numpy()))

gt = (
    GT(tbl, rowname_col="car")
    # ------------------------------------------------ Step 6: titles & notes
    .tab_header(
        title="Horsepower and Price Across the GT Cars",
        subtitle="All 47 cars in the gtcars collection, ranked by peak horsepower",
    )
    .tab_stubhead(label="Car")
    .cols_label(year="Year", hp="Horsepower", msrp="Price (MSRP)")
    # ------------------------------------------- Step 5(e): format per column
    .fmt_integer(columns=["hp"])
    .fmt_currency(columns=["msrp"], currency="USD", decimals=0)
    .fmt_integer(columns=["year"], use_seps=False)  # 2,017 is wrong for a year
    .sub_missing(columns=["year", "hp", "msrp"], missing_text="—")
    # ------------------------------------------------------ Step 3: Big Color
    .data_color(
        columns=["hp"],
        palette="Blues",  # neutral magnitude, primary measure
        domain=[hp_lo, hp_hi],
        truncate=False,
        na_color="#808080",
    )
    .data_color(
        columns=["msrp"],
        palette="Greens",  # secondary neutral -> next rung of the ladder
        domain=[msrp_lo, msrp_hi],
        truncate=False,
        na_color="#808080",
    )
    # ------------------------------------------------ Step 5(c): row striping
    # >=10 rows and the body is not essentially fully filled (stub + Year are plain).
    .opt_row_striping()
    .tab_options(row_striping_background_color="#F6F6F6")
    # --------------------------------------------------- Step 5(d): stub tint
    # Grey-budget rule: band + stripes + stub would stack three greys, so the
    # highest-priority element (the stub) takes the washed-Blues tint.
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    .tab_style(style=style.text(weight="bold"), locations=loc.stub())
    .cols_align(align="right", columns=["year", "hp", "msrp"])
    # ------------------------------------------------ Step 6: stacked footers
    .tab_source_note(
        source_note=(
            "Cell shading encodes magnitude within each column: horsepower in blue, "
            "price in green. Price is the manufacturer's suggested retail price in USD."
        )
    )
    .tab_source_note(source_note="Source: gtcars dataset (Posit / great_tables sample data).")
    .tab_options(
        # Step 4: LIGHT heading band (Big Color present) + the 2px bottom rule
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): hairline between every body row
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame: light boxed border on all four sides (left/right default to none)
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

# ------------------------------------------------------- Step 7: render & save
gt.gtsave("table.png", expand=15, zoom=2.0, vwidth=1000, vheight=1800)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("wrote table.png and table.html")
