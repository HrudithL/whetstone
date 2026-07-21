"""Monthly air-quality summary built with great_tables.

Grain of source: one row per day (New York, May-Sep 1973 -- base R `airquality`).
We aggregate to one row per month and report the mean of each daily reading,
skipping missing observations (pandas .mean() drops NaN).

Big Color: three neutral magnitudes qualify (Temperature, Wind, Ozone) over 5
rows, so the >=5-row gradient rule makes each eligible; the <=2 ceiling colours
exactly two. Prompt order (temperature, wind speed, ozone) selects Temperature
(primary -> Blues) and Wind (secondary -> Greens by the neutral tie-breaker
ladder). Ozone is carried by the number alone. Big Color present => LIGHT band.
"""

import numpy as np
import pandas as pd
from great_tables import GT, md, loc, style

# ---- Step 1: understand + clean -> one correctly-typed DataFrame ----------
raw = pd.read_csv("airquality.csv")

MONTHS = {5: "May", 6: "June", 7: "July", 8: "August", 9: "September"}

monthly = (
    raw.groupby("Month")
    .agg(avg_temp=("Temp", "mean"),
         avg_wind=("Wind", "mean"),
         avg_ozone=("Ozone", "mean"))
    .reset_index()
    .sort_values("Month")
)
monthly["Month"] = monthly["Month"].map(MONTHS)
df = monthly[["Month", "avg_temp", "avg_wind", "avg_ozone"]].reset_index(drop=True)

# ---- Step 3: Big Color -- data-driven, one shared domain per measure ------
temp_cols = ["avg_temp"]
wind_cols = ["avg_wind"]
temp_lo = float(np.nanmin(df[temp_cols].to_numpy()))
temp_hi = float(np.nanmax(df[temp_cols].to_numpy()))
wind_lo = float(np.nanmin(df[wind_cols].to_numpy()))
wind_hi = float(np.nanmax(df[wind_cols].to_numpy()))

# ---- Steps 2, 4, 5, 6: build the whole table in one chained expression ----
gt = (
    GT(df, rowname_col="Month")                       # Step 2: Month is the stub
    .tab_header(
        title="New York Air Quality by Month",
        subtitle=md("Monthly means of daily readings &mdash; May to September 1973"),
    )
    .tab_spanner(
        label="Monthly average conditions",
        columns=["avg_temp", "avg_wind", "avg_ozone"],
    )
    .cols_label(
        avg_temp=md("Temperature<br>(&deg;F)"),
        avg_wind=md("Wind speed<br>(mph)"),
        avg_ozone=md("Ozone<br>(ppb)"),
    )
    .tab_stubhead(label="Month")
    # Step 5(e): meaningful precision, thousands seps, missing glyph
    .fmt_number(columns=["avg_temp", "avg_wind", "avg_ozone"], decimals=1, use_seps=True)
    .sub_missing(columns=["avg_temp", "avg_wind", "avg_ozone"], missing_text="—")
    .cols_align(align="center", columns=["avg_temp", "avg_wind", "avg_ozone"])
    # Step 3: colour the two selected measures (Temperature -> Blues, Wind -> Greens)
    .data_color(
        columns=temp_cols, palette="Blues",
        domain=[temp_lo, temp_hi], truncate=False, na_color="#808080",
    )
    .data_color(
        columns=wind_cols, palette="Greens",
        domain=[wind_lo, wind_hi], truncate=False, na_color="#808080",
    )
    # Step 4: LIGHT heading band (washed tint of dominant Blues hue) + bottom rule
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): hairline between body rows
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame: boxed light border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # Step 5(d): stub tint (grey default -- band already carries the washed blue)
    .tab_style(style=style.fill(color="#F0F0F0"), locations=loc.stub())
    .tab_style(style=style.text(weight="bold"), locations=loc.stub())
    # Step 6: source note (>=5 rows) -- state the canonical metric
    .tab_source_note(
        source_note=md(
            "Values are means of available daily observations; missing days are "
            "excluded. Source: base R `airquality` (New York, 1973)."
        )
    )
)

# ---- Step 7: render the real PNG + the embeddable HTML --------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print(df.to_string(index=False))
print("\nWrote table.png and table.html")
