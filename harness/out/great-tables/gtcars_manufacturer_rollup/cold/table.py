"""Build a GT-cars table showing horsepower and price, grouped by manufacturer.

Design follows the great-tables flowchart:
  Step 1  clean, correctly-typed DataFrame (one row per car)
  Step 2  organize: group by manufacturer (stub = model), show hp + price only
  Step 3  Big Color: two neutral magnitudes -> hp = Blues (primary), price = Greens
  Step 4  heading band: Big Color present -> LIGHT washed-blue band
  Step 5  Small-Color polish: hairlines, stub tint, group emphasis, fmt per type
  Step 6  title + subtitle + source note
  Step 7  render with .gtsave("table.png") and also emit table.html
"""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------------------
# Step 1 — Understand & clean the data
# ---------------------------------------------------------------------------
# gtcars.csv is already correctly typed (hp/msrp are floats). Grain: one row
# per car; identifiers: mfr + model; requested measures: hp (horsepower), msrp (price).
df = pd.read_csv("gtcars.csv")

# ---------------------------------------------------------------------------
# Step 2 — Organize columns
# ---------------------------------------------------------------------------
# Keep only the identifiers and the two requested measures. Manufacturer is the
# organizing story (groupname_col); model is the row identifier (stub).
# Sort so groups are contiguous (mfr A->Z) and within each group the most
# powerful car comes first.
cars = (
    df[["mfr", "model", "hp", "msrp"]]
    .sort_values(["mfr", "hp"], ascending=[True, False])
    .reset_index(drop=True)
)

# ---------------------------------------------------------------------------
# Step 3 — Big Color domains (data-driven, backend-neutral)
# ---------------------------------------------------------------------------
hp_lo = float(np.nanmin(cars[["hp"]].to_numpy()))
hp_hi = float(np.nanmax(cars[["hp"]].to_numpy()))
msrp_lo = float(np.nanmin(cars[["msrp"]].to_numpy()))
msrp_hi = float(np.nanmax(cars[["msrp"]].to_numpy()))

# Washed-blue tint (dominant Big-Color hue = Blues) used for all light surfaces.
WASHED_BLUE = "#EAF0F6"

gt = (
    GT(cars, rowname_col="model", groupname_col="mfr")
    # -- Step 6: titles / subtitle ------------------------------------------
    .tab_header(
        title=md("**GT Cars — Horsepower & Price**"),
        subtitle="Engine output and manufacturer's suggested retail price, by marque",
    )
    .tab_stubhead(label="Model")
    # -- Step 5(e): format per semantic type --------------------------------
    .fmt_number(columns="hp", decimals=0, use_seps=True)
    .fmt_currency(columns="msrp", currency="USD", decimals=0, use_seps=True)
    .cols_label(hp="Horsepower", msrp="Price (MSRP)")
    # -- Step 3: Big Color — two neutral magnitudes -------------------------
    # Primary measure (horsepower, named first in the prompt) -> Blues.
    .data_color(
        columns="hp",
        palette="Blues",
        domain=[hp_lo, hp_hi],
        truncate=False,
        na_color="#808080",
    )
    # Secondary neutral magnitude (price) -> next rung of the ladder: Greens.
    .data_color(
        columns="msrp",
        palette="Greens",
        domain=[msrp_lo, msrp_hi],
        truncate=False,
        na_color="#808080",
    )
    # -- Step 4: LIGHT heading band (Big Color present) ---------------------
    .tab_options(
        column_labels_background_color=WASHED_BLUE,
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): cell hairlines between body rows
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Step 5 sub-note: row-group (manufacturer) emphasis
        row_group_background_color=WASHED_BLUE,
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # Frame: boxed light border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # -- Step 5(d): stub tint (harmonized to the washed-blue theme) ---------
    .tab_style(
        style=style.fill(color=WASHED_BLUE),
        locations=loc.stub(),
    )
    # -- Step 6: source note (dataset is known) -----------------------------
    .tab_source_note(
        source_note=md(
            "_Source:_ `gtcars` dataset (47 grand-touring models) — "
            "horsepower measured in hp; price is USD MSRP."
        )
    )
)

# ---------------------------------------------------------------------------
# Step 7 — Render (mandatory PNG) + self-contained HTML
# ---------------------------------------------------------------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w", encoding="utf-8") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
