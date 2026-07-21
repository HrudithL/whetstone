"""Build a table of the world's landmasses/islands and their sizes with great_tables."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# --- Step 1: understand + clean the data -> ONE correctly-typed DataFrame -----
df = pd.read_csv("islands.csv")
df["size"] = pd.to_numeric(df["size"], errors="coerce")  # ensure numeric measure
# Order by magnitude so the sequential gradient reads top-to-bottom.
df = df.sort_values("size", ascending=False).reset_index(drop=True)

# --- Step 3: Big Color — single ordered magnitude => column gradient fill -----
measure = ["size"]
lo = float(np.nanmin(df[measure].to_numpy()))
hi = float(np.nanmax(df[measure].to_numpy()))

gt = (
    GT(df, rowname_col="name")                         # Step 2: name IS the stub
    .tab_header(
        title="The Islands of the World",
        subtitle="Land areas of major landmasses and islands, ranked largest to smallest",
    )
    .cols_label(size="Area")
    .tab_stubhead(label="Landmass")
    # Step 3: sequential Blues gradient (neutral magnitude), one shared data-driven domain
    .fmt_number(columns="size", decimals=0, use_seps=True)
    .data_color(
        columns="size",
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # --- Step 4: LIGHT heading band (Big Color present) -> washed Blues tint ---
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5 (a): body hairlines
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Step 5 (c): row striping (>=10 rows, body not fully Big-Color filled)
        row_striping_background_color="#F6F6F6",
        # Frame — boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    .opt_row_striping()
    # Step 5 (d): stub tint — harmonized to washed-Blues per the grey-budget rule
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    # Step 6: caption (>=5 rows) + source note
    .tab_source_note(source_note=md("Areas are given in **thousands of square miles**."))
    .tab_source_note(source_note=md("Source: R `datasets::islands`."))
)

# --- Step 7: render the real PNG + write self-contained HTML -------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print(f"Rendered {len(df)} islands. Size domain: [{lo:.0f}, {hi:.0f}].")
