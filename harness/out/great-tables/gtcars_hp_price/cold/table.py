"""GT cars — model, horsepower, and price, built with great_tables."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# --- Step 1: understand + clean the data ------------------------------------
# One row per car. Identifiers: mfr + model. Measures: hp (horsepower), msrp (price).
# CSV values already parse to numeric floats (no currency strings), no missing values.
raw = pd.read_csv("gtcars.csv")

df = (
    raw.assign(car=raw["mfr"].str.strip() + " " + raw["model"].str.strip())
    .loc[:, ["car", "hp", "msrp"]]
    .sort_values("hp", ascending=False)  # order by the hero measure so the gradient reads top-down
    .reset_index(drop=True)
)

# --- Step 3: Big Color — two neutral magnitude measures ---------------------
# Neutral tie-breaker ladder (Blues -> Greens): primary hp = Blues, secondary price = Greens.
hp_lo = float(np.nanmin(df[["hp"]].to_numpy()))
hp_hi = float(np.nanmax(df[["hp"]].to_numpy()))
msrp_lo = float(np.nanmin(df[["msrp"]].to_numpy()))
msrp_hi = float(np.nanmax(df[["msrp"]].to_numpy()))

# --- Steps 2, 4, 5, 6: build the table --------------------------------------
gt = (
    GT(df, rowname_col="car")
    .tab_header(
        title="Grand Tourers by the Numbers",
        subtitle="Horsepower and list price for 47 GT cars, ranked by peak output",
    )
    .tab_stubhead(label="Model")
    .cols_label(hp="Horsepower", msrp="Price")
    # Step 5(e): format each measure to its semantic type
    .fmt_number(columns="hp", decimals=0, use_seps=True)
    .fmt_currency(columns="msrp", decimals=0, use_seps=True)
    # Step 3: gradient fills (each measure its own domain + semantic hue)
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
    # Step 5(d): stub tint harmonized to the dominant Blues hue (washed-DA)
    .tab_style(
        style=style.fill(color="#EAF0F6"),
        locations=loc.stub(),
    )
    # Step 6: source note (>=5 rows)
    .tab_source_note(
        source_note=md("Source: the *gtcars* dataset. Price is manufacturer's suggested retail price (MSRP).")
    )
    # Step 4: LIGHT heading band (washed-DA Blues tint) + Step 5(a) borders + Frame
    .tab_options(
        # light heading band
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # body hairlines
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # four-side Frame
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# --- Step 7: render (mandatory PNG) + self-contained HTML --------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
