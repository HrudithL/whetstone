"""Monthly air-quality summary — average Temp, Wind, and Ozone per month.

Built with great_tables following the skill's 7-step flowchart.

Design notes:
- Step 1-2: aggregate to one row per month (May-Sep). The Month column holds
  row identifiers -> it IS the stub. Three measures (Temp, Wind, Ozone), units
  carried in the column labels.
- Step 3 Big Color: the learned dark-green header band anchors the table, and a
  dark saturated band means NO Big Color body fills (they would fight for the
  anchor role). Green is also the correct Forest/environment subject hue.
- Step 4: dark-green heading band (#0B6E4F) with white bold text.
- Step 5: grey stub tint, cell hairlines, 1-decimal numbers, frame border,
  source note. No row striping (<10 rows).
"""

import pandas as pd
from great_tables import GT, style, loc

# --- Step 1: understand + clean --------------------------------------------
# CSV is already correctly typed (Ozone/Wind float, Temp/Month int); Ozone has
# NaNs which .mean() skips by default.
df = pd.read_csv("airquality.csv")

MONTHS = {5: "May", 6: "June", 7: "July", 8: "August", 9: "September"}

summary = (
    df.groupby("Month", as_index=False)[["Temp", "Wind", "Ozone"]]
    .mean()
    .sort_values("Month")
)
summary["Month"] = summary["Month"].map(MONTHS)

# --- Steps 2-6: organize + style -------------------------------------------
BAND = "#0B6E4F"   # dark-green heading band (learned preference)

gt = (
    GT(summary, rowname_col="Month")
    .tab_header(
        title="Monthly Air-Quality Summary",
        subtitle="Average temperature, wind speed, and ozone level by month",
    )
    .cols_label(
        Temp="Temperature (°F)",
        Wind="Wind Speed (mph)",
        Ozone="Ozone (ppb)",
    )
    .tab_stubhead(label="Month")
    # Step 5(e): one-decimal numbers (learned preference L1)
    .fmt_number(columns=["Temp", "Wind", "Ozone"], decimals=1)
    .sub_missing(columns=["Temp", "Wind", "Ozone"], missing_text="—")
    .cols_align(align="center", columns=["Temp", "Wind", "Ozone"])
    # Step 4: dark-green header band, white text (learned preference L2)
    .tab_style(
        style=[style.fill(color=BAND), style.text(color="white", weight="bold")],
        locations=loc.column_labels(),
    )
    .tab_style(
        style=[style.fill(color=BAND), style.text(color="white", weight="bold")],
        locations=loc.stubhead(),
    )
    # Step 5(d): grey stub tint
    .tab_style(
        style=style.fill(color="#F0F0F0"),
        locations=loc.stub(),
    )
    # Step 6: source note
    .tab_source_note(
        source_note="Source: New York air-quality measurements, May-September 1973. "
        "Values are monthly means (ozone means exclude missing days)."
    )
    # Step 5(a): cell hairlines + column-label bottom rule
    .tab_options(
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Frame: boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# --- Step 7: render + additional HTML artifact -----------------------------
gt.gtsave("table.png", expand=15)

with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
print(summary.to_string(index=False))
