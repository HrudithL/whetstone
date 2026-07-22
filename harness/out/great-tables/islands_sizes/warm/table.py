import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# --- Step 1: understand + clean the data -------------------------------------
# Two columns: name (row identifier) and size (an ordered numeric magnitude).
# The classic R `islands` dataset reports areas in thousands of square miles.
df = pd.read_csv("islands.csv")
df["size"] = pd.to_numeric(df["size"], errors="coerce")

# Learned preference: order rows by size, largest to smallest.
df = df.sort_values("size", ascending=False).reset_index(drop=True)

# --- Step 3: Big Color — gradient fill on the size measure -------------------
# Data-driven, backend-neutral domain across the single measure column.
cols = ["size"]
lo = float(np.nanmin(df[cols].to_numpy()))
hi = float(np.nanmax(df[cols].to_numpy()))

# Washed purple to harmonize the light chrome with the Purples gradient.
BAND_PURPLE = "#EFEDF5"

gt = (
    GT(df, rowname_col="name")                       # Step 2: name is the stub
    .tab_header(
        title="The World's Major Landmasses",
        subtitle="Continents and islands ranked by surface area",
    )
    .tab_stubhead(label="Landmass")
    .cols_label(size="Area")
    # Step 5(e): format the measure
    .fmt_number(columns="size", decimals=0, use_seps=True)
    .sub_missing(columns="size", missing_text="—")
    # Step 3: heat-map the size column with the Purples ramp (user request)
    .data_color(
        columns="size",
        palette="Purples",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 5(d): stub tint, harmonized to the washed-purple hue
    .tab_style(
        style=style.fill(color=BAND_PURPLE),
        locations=loc.stub(),
    )
    # Step 6: caption (>=5 rows) + source
    .tab_source_note(
        source_note=md(
            "Areas in thousands of square miles. Source: R `datasets::islands` "
            "(The World Almanac and Book of Facts, 1975)."
        )
    )
    # Step 4: LIGHT heading band (Big Color present) + Step 5(a) borders + Frame
    .tab_options(
        # Light heading band, dark bold labels
        column_labels_background_color=BAND_PURPLE,
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Row hairlines
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

# --- Step 7: render + additional HTML artifact -------------------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
