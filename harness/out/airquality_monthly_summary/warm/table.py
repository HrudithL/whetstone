"""Monthly air-quality summary table built with great_tables.

Grain: one row per month (May–September). Three requested measures
(average temperature, wind speed, ozone). All three qualify as ordered
magnitudes, but the Big-Color ceiling is <=2 colored measures, so by prompt
order Temperature + Wind are colored (Blues primary / Greens secondary neutral
tie-breaker) and Ozone is carried by its number alone.
"""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# --- Step 1: understand + clean the data -> one correctly-typed DataFrame ----
raw = pd.read_csv("airquality.csv")

summary = (
    raw.groupby("Month", as_index=False)[["Temp", "Wind", "Ozone"]]
    .mean()
    .sort_values("Month")
)

MONTH_NAMES = {5: "May", 6: "June", 7: "July", 8: "August", 9: "September"}
summary["Month"] = summary["Month"].map(MONTH_NAMES)

# --- Step 3: Big Color domains (data-driven, backend-neutral) ----------------
temp_lo = float(np.nanmin(summary[["Temp"]].to_numpy()))
temp_hi = float(np.nanmax(summary[["Temp"]].to_numpy()))
wind_lo = float(np.nanmin(summary[["Wind"]].to_numpy()))
wind_hi = float(np.nanmax(summary[["Wind"]].to_numpy()))

# --- Build the table ---------------------------------------------------------
gt = (
    GT(summary, rowname_col="Month")                       # Step 2: Month is the stub
    .tab_header(
        title="New York Air Quality by Month",
        subtitle="Average temperature, wind speed, and ozone (May–September 1973)",
    )
    .cols_label(
        Temp=md("Temperature<br>(°F)"),
        Wind=md("Wind Speed<br>(mph)"),
        Ozone=md("Ozone<br>(ppb)"),
    )
    .tab_stubhead(label="Month")
    # Step 5(e): format every value column to one decimal
    .fmt_number(columns=["Temp", "Wind", "Ozone"], decimals=1)
    .sub_missing(columns=["Temp", "Wind", "Ozone"], missing_text="—")
    # Step 3: Big Color — Temperature (Blues, primary neutral)
    .data_color(
        columns=["Temp"],
        palette="Blues",
        domain=[temp_lo, temp_hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 3: Big Color — Wind (Greens, secondary neutral tie-breaker)
    .data_color(
        columns=["Wind"],
        palette="Greens",
        domain=[wind_lo, wind_hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 4: Big Color present -> LIGHT heading band (grey; two Big-Color hues)
    .tab_options(
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): cell hairlines between rows
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame: boxed enclosing light border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # Step 5(d): stub tint (grey default)
    .tab_style(
        style=style.fill(color="#F0F0F0"),
        locations=loc.stub(),
    )
    # Step 6: source note (dataset provenance is known)
    .tab_source_note(
        source_note=md(
            "Source: New York air-quality measurements, May–September 1973 "
            "(`airquality` dataset). Monthly means; ozone averaged over available readings."
        )
    )
)

# --- Step 7: render + additional HTML artifact -------------------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
