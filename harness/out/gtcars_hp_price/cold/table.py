"""Build a Great Tables display of GT cars with horsepower and price."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------------------
# Step 1 — Understand & clean the data → ONE correctly-typed DataFrame
# Grain: one row per car. Identifiers: mfr + model. Measures: hp, msrp (price).
# ---------------------------------------------------------------------------
df = pd.read_csv("gtcars.csv")

# Coerce the requested numeric measures deliberately (they arrive as floats,
# but coercion guards against any stray non-numeric tokens).
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")

# Trim whitespace on the string keys used for grouping / the stub.
df["mfr"] = df["mfr"].astype(str).str.strip()
df["model"] = df["model"].astype(str).str.strip()

# Keep only what the request needs, ordered: manufacturer group, then hp desc.
df = (
    df[["mfr", "model", "hp", "msrp"]]
    .sort_values(["mfr", "hp"], ascending=[True, False])
    .reset_index(drop=True)
)

# ---------------------------------------------------------------------------
# Step 3 — Big Color: two neutral magnitudes → color BOTH.
# Tie-breaker (palettes.md §3): primary neutral keeps Blues, secondary → Greens.
# Prompt names horsepower first ⇒ hp = primary (Blues); price = secondary (Greens).
# Data-driven domains, one per measure.
# ---------------------------------------------------------------------------
hp_lo = float(np.nanmin(df[["hp"]].to_numpy()))
hp_hi = float(np.nanmax(df[["hp"]].to_numpy()))
price_lo = float(np.nanmin(df[["msrp"]].to_numpy()))
price_hi = float(np.nanmax(df[["msrp"]].to_numpy()))

# ---------------------------------------------------------------------------
# Steps 2 + 4 + 5 + 6 — organize, band, polish, titles (one chained build)
# ---------------------------------------------------------------------------
gt = (
    GT(df, rowname_col="model", groupname_col="mfr")
    # Step 6 — title + subtitle (both required) + source note
    .tab_header(
        title="GT Cars — Horsepower & Price",
        subtitle="Peak power output and manufacturer's suggested retail price, by marque",
    )
    .tab_stubhead(label="Model")
    .tab_source_note(source_note=md("Source: the **gtcars** dataset (`gtcars.csv`)."))
    .tab_source_note(
        source_note="Rows shaded by magnitude: horsepower in blue, price in green."
    )
    # Step 5(e) — format per semantic type
    .fmt_number(columns="hp", decimals=0, use_seps=True)
    .fmt_currency(columns="msrp", decimals=0, use_seps=True)
    .sub_missing(columns=["hp", "msrp"], missing_text="—")
    .cols_label(hp="Horsepower", msrp="Price (MSRP)")
    .cols_align(align="right", columns=["hp", "msrp"])
    # Step 3 — gradient fills, primary hue = Blues, secondary = Greens
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
        domain=[price_lo, price_hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 4 — LIGHT band (washed pale-blue of the primary Big-Color hue)
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a) — hairlines between rows
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Step 5 sub-note — row-group emphasis (fill + bold, structural rule)
        row_group_background_color="#F0F0F0",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # Frame — square light enclosing border on all four sides
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
    # Step 5(d) — stub tint (grey default; band carries the washed tint)
    .tab_style(style=style.fill(color="#F0F0F0"), locations=loc.stub())
)

# ---------------------------------------------------------------------------
# Step 7 — Render the mandatory PNG, plus the embeddable HTML artifact
# ---------------------------------------------------------------------------
gt.gtsave("table.png", expand=15, vwidth=900, vheight=1400, zoom=2.0)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
