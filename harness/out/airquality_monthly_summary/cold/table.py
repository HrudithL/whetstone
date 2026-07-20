"""Monthly air-quality summary — average Temp, Wind, and Ozone per month.

Data:  airquality.csv (NYC daily readings, May–September 1973)
Table: one row per month; averages of temperature, wind speed, and ozone.
Built with great_tables per the 7-step flowchart.
"""
import numpy as np
import pandas as pd
from great_tables import GT, html, style, loc

# ── Step 1 — UNDERSTAND & CLEAN ────────────────────────────────────────────
# Grain of the source is one daily reading; the request wants one row per
# month, so aggregate to monthly means. Ozone/Wind/Temp are already numeric.
# Means skip NaN by default (pandas), so missing daily readings are excluded.
df = pd.read_csv("airquality.csv")

month_name = {5: "May", 6: "June", 7: "July", 8: "August", 9: "September"}

monthly = (
    df.groupby("Month")
      .agg(temp_mean=("Temp", "mean"),
           wind_mean=("Wind", "mean"),
           ozone_mean=("Ozone", "mean"))
      .reset_index()
)
monthly["month_label"] = monthly["Month"].map(month_name)

# ── Step 2 — ORGANIZE COLUMNS ──────────────────────────────────────────────
# Stub = month identifier (PP-13). Columns in prompt order: temp, wind, ozone.
monthly = monthly[["month_label", "temp_mean", "wind_mean", "ozone_mean"]]

# ── Step 3 — BIG COLOR ─────────────────────────────────────────────────────
# Three ordered magnitudes over 5 rows all qualify, but the ceiling is 2.
# Prompt names temperature first, wind second → colour those two.
# Both are NEUTRAL magnitudes → primary (temp) keeps Blues, secondary (wind)
# takes the next distinct hue Greens. Ozone stays uncoloured (number only).
temp_lo = float(np.nanmin(monthly[["temp_mean"]].to_numpy()))
temp_hi = float(np.nanmax(monthly[["temp_mean"]].to_numpy()))
wind_lo = float(np.nanmin(monthly[["wind_mean"]].to_numpy()))
wind_hi = float(np.nanmax(monthly[["wind_mean"]].to_numpy()))

gt = (
    GT(monthly, rowname_col="month_label")
    # ── Step 6 — TITLES ────────────────────────────────────────────────────
    .tab_header(
        title="New York Air Quality by Month",
        subtitle="Average temperature, wind speed, and ozone — May–September 1973",
    )
    .cols_label(
        temp_mean=html("Temperature<br>(&deg;F)"),
        wind_mean=html("Wind speed<br>(mph)"),
        ozone_mean=html("Ozone<br>(ppb)"),
    )
    # ── Step 5(e) — FORMAT PER COLUMN ───────────────────────────────────────
    .fmt_number(columns=["temp_mean", "wind_mean", "ozone_mean"], decimals=1)
    .sub_missing(columns=["temp_mean", "wind_mean", "ozone_mean"], missing_text="—")
    # Big Color: two neutral measures, distinct hues, per-measure domains.
    .data_color(columns=["temp_mean"], palette="Blues",
                domain=[temp_lo, temp_hi], truncate=False, na_color="#808080")
    .data_color(columns=["wind_mean"], palette="Greens",
                domain=[wind_lo, wind_hi], truncate=False, na_color="#808080")
    # ── Step 4 — LIGHT heading band (Big Color present) ─────────────────────
    # Washed tint of the dominant Blues hue; dark bold labels.
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # (a) cell hairlines between every body row
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Frame — boxed enclosing border on all four sides
        table_border_top_style="solid",    table_border_top_color="#CCCCCC",    table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid",   table_border_left_color="#CCCCCC",   table_border_left_width="1px",
        table_border_right_style="solid",  table_border_right_color="#CCCCCC",  table_border_right_width="1px",
    )
    # ── Step 5(d) — stub tint harmonized to the Blues washed tint ───────────
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    .tab_stubhead(label="Month")
    .cols_align(align="center", columns=["temp_mean", "wind_mean", "ozone_mean"])
    # ── Step 6 — source / caption ───────────────────────────────────────────
    .tab_source_note(
        source_note="Averages computed over available daily readings; missing values excluded."
    )
    .tab_source_note(
        source_note="Source: New York State Department of Conservation & NASA — daily measurements, May–September 1973."
    )
)

# ── Step 7 — RENDER & VERIFY ────────────────────────────────────────────────
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())
print("Wrote table.png and table.html")
