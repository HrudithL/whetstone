"""Build a publication-ready table of the world's landmasses and their areas."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# --- Step 1: one clean, correctly-typed DataFrame ---------------------------
df = pd.read_csv("islands.csv")
df["size"] = pd.to_numeric(df["size"], errors="coerce")  # ensure numeric measure

# --- Step 2: organize columns -----------------------------------------------
# `name` is the row identifier -> stub. Order by magnitude (largest first).
df = df.sort_values("size", ascending=False).reset_index(drop=True)

# --- Step 3: Big Color — single ordered magnitude, >=5 rows -> gradient fill -
cols = ["size"]
lo = float(np.nanmin(df[cols].to_numpy()))
hi = float(np.nanmax(df[cols].to_numpy()))

gt = (
    GT(df, rowname_col="name")
    .cols_label(size="Area (thousands of sq mi)")
    # Step 6: titles/annotations (both required) + source note
    .tab_header(
        title="The World's Major Landmasses by Area",
        subtitle="Continents and large islands, ranked from largest to smallest.",
    )
    .tab_source_note(
        source_note=md(
            "Areas are given in **thousands of square miles**. "
            "Source: R `datasets::islands` (The World Almanac and Book of Facts, 1975)."
        )
    )
    # Step 5(e): format the measure
    .fmt_number(columns=cols, decimals=0, use_seps=True)
    .sub_missing(columns=cols, missing_text="—")
    # Step 3: gradient fill on the hero measure
    .data_color(
        columns=cols,
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 5(a): cell hairlines + column-label bottom rule
    .tab_options(
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 4: LIGHT heading band (washed Blues tint) — table has Big Color
        heading_background_color="#EAF0F6",
        column_labels_background_color="#EAF0F6",
        # Step 5(c): row striping (48 rows, body not fully filled)
        row_striping_background_color="#F6F6F6",
    )
    .opt_row_striping()
    # Step 5(d): stub tint — harmonized to washed Blues (grey-budget rule)
    .tab_style(
        style=style.fill(color="#EAF0F6"),
        locations=loc.stub(),
    )
    .tab_stubhead(label="Landmass")
    # Frame: boxed light border on all four sides
    .tab_options(
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# --- Step 7: render + self-contained HTML -----------------------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
