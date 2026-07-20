"""Build a Great Tables table of the gtcars: horsepower and price, grouped by
manufacturer. Follows the great-tables skill flowchart."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------- Step 1: data
df = pd.read_csv("gtcars.csv")

# hp and msrp import as clean floats; keep only what the request needs.
df = df[["mfr", "model", "hp", "msrp"]].copy()
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")

# ------------------------------------------------------ Step 2: organize columns
# Manufacturer is the low-cardinality organizing categorical -> group.
# Model is the per-row identifier -> stub.
# Sort by manufacturer, then price (desc) so each group reads high->low.
df = df.sort_values(["mfr", "msrp"], ascending=[True, False]).reset_index(drop=True)

# ------------------------------------------------------------- Step 3: Big Color
# Two neutral magnitudes (both qualify, <= 2). Tie-breaker (palettes.md sec 3):
#   hp   -> primary (prompt-named first) -> Blues
#   msrp -> secondary neutral            -> Greens
hp_lo = float(np.nanmin(df[["hp"]].to_numpy()))
hp_hi = float(np.nanmax(df[["hp"]].to_numpy()))
msrp_lo = float(np.nanmin(df[["msrp"]].to_numpy()))
msrp_hi = float(np.nanmax(df[["msrp"]].to_numpy()))

gt = (
    GT(df, rowname_col="model", groupname_col="mfr")
    # ----------------------------------------------- Step 2: labels & stubhead
    .cols_label(hp="Horsepower", msrp="Price (MSRP)")
    .tab_stubhead(label="Model")
    # --------------------------------------------------- Step 3: gradient fills
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
    # ------------------------------------------------------- Step 5: formatting
    .fmt_number(columns="hp", decimals=0, use_seps=True)
    .fmt_currency(columns="msrp", decimals=0, use_seps=True)  # US$, no decimals (L1)
    .sub_missing(missing_text="—")
    # ---------------------------------------------- Step 6: titles & source note
    .tab_header(
        title=md("**The GT Cars**"),
        subtitle="Horsepower and manufacturer's suggested retail price, by marque",
    )
    .tab_source_note(source_note=md("Source: the **gtcars** dataset (47 grand-touring cars)."))
    # ------------------------------------ Step 4: LIGHT band (Big Color present)
    .tab_options(
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): hairlines between rows
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Step 5 sub-note: row-group emphasis (fill + bold)
        row_group_background_color="#F0F0F0",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # Frame: boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # Step 5(d): stub tint (grey default; two Big-Color hues -> stay neutral grey)
    .tab_style(style=style.fill(color="#F0F0F0"), locations=loc.stub())
    .cols_align(align="center", columns=["hp", "msrp"])
)

# --------------------------------------------------------- Step 7: render & save
html = gt.as_raw_html()
with open("table.html", "w") as f:
    f.write(html)

gt.gtsave("table.png", expand=15)
print("Wrote table.png and table.html")
