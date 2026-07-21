import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# --- Step 1: understand + clean data -> one correctly-typed DataFrame ---
df = pd.read_csv("islands.csv")
df["size"] = pd.to_numeric(df["size"], errors="coerce")  # ensure numeric measure

# --- Step 2: organize columns ---
# order rows by size, largest -> smallest
df = df.sort_values("size", ascending=False).reset_index(drop=True)

# --- Step 3: Big Color -> Blues gradient on the single ordered magnitude ---
cols = ["size"]
lo = float(np.nanmin(df[cols].to_numpy()))
hi = float(np.nanmax(df[cols].to_numpy()))

BAND = "#EAF0F6"  # washed-Blues light band / stub tint

gt = (
    GT(df, rowname_col="name")
    .tab_header(
        title="The Landmasses of the World",
        subtitle="Continents and major islands ranked by area",
    )
    # Step 5(e): format the measure
    .fmt_number(columns="size", decimals=0, use_seps=True)
    .cols_label(size=md("Area<br>(1,000 mi²)"))
    # Step 3: column gradient fill
    .data_color(
        columns="size",
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    .tab_stubhead(label="Landmass")
    # Step 4: LIGHT heading band (Big Color present)
    .tab_options(
        column_labels_background_color=BAND,
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): hairline between every body row
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
    )
    # Step 5(d): stub tint, harmonized to the Blues washed tint (grey-budget)
    .tab_style(
        style=style.fill(color=BAND),
        locations=loc.stub(),
    )
    # Step 6: caption (>=5 rows) + source note
    .tab_source_note(
        source_note=md(
            "Source: R `islands` dataset. Areas are given in thousands of square miles."
        )
    )
    # Frame: boxed enclosing light border on all four sides
    .tab_options(
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# --- Step 7: render + additional HTML artifact ---
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
