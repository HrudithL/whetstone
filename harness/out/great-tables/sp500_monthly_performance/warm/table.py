"""S&P 500 monthly performance summary, 2010–2015.

Built with great_tables per the skill flowchart.
Big Color: the monthly % change column is heat-mapped with the warm
ColorBrewer YlOrRd ramp (learned preference). One colored measure -> LIGHT
heading band. Negatives render accounting-style (parentheses).
"""
import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---- Step 1: understand + clean the data ---------------------------------
raw = pd.read_csv("sp500.csv", parse_dates=["date"]).sort_values("date")

# Canonical definition of a "single-day gain/loss": the close-to-close daily
# return, computed across the full series so the first trading day of each
# month has a valid prior-close reference. Stated in a source note.
raw["daily_return"] = raw["close"].pct_change()

raw["year"] = raw["date"].dt.year
raw["month"] = raw["date"].dt.month

window = raw[(raw["year"] >= 2010) & (raw["year"] <= 2015)].copy()

MONTHS = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
          7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

rows = []
for (yr, mo), grp in window.groupby(["year", "month"], sort=True):
    grp = grp.sort_values("date")
    open_px = grp["open"].iloc[0]
    close_px = grp["close"].iloc[-1]
    rows.append({
        "year": str(yr),
        "month": MONTHS[mo],
        "open_px": open_px,
        "close_px": close_px,
        "pct_change": close_px / open_px - 1.0,
        "avg_volume": grp["volume"].mean(),
        "best_day": grp["daily_return"].max(),
        "worst_day": grp["daily_return"].min(),
    })

monthly = pd.DataFrame(rows)

# ---- Step 3: Big Color domain (data-driven, one shared domain) ------------
COLOR_COLS = ["pct_change"]
lo = float(np.nanmin(monthly[COLOR_COLS].to_numpy()))
hi = float(np.nanmax(monthly[COLOR_COLS].to_numpy()))

# Warm washed tint echoing the YlOrRd (Oxblood family) big color.
WARM_TINT = "#F5EBEB"
GREY_BAND = "#F0F0F0"

# ---- Steps 2, 4, 5, 6: build the table -----------------------------------
gt = (
    GT(monthly, rowname_col="month", groupname_col="year")
    .tab_header(
        title="S&P 500 — Monthly Performance Summary",
        subtitle=md("Opening & closing levels, monthly change, and daily trading "
                    "extremes · **2010–2015**"),
    )
    .tab_stubhead(label="Month")
    .tab_spanner(label="Index Level", columns=["open_px", "close_px"])
    .tab_spanner(label="Largest Single-Day Move", columns=["best_day", "worst_day"])
    .cols_label(
        open_px="Open",
        close_px="Close",
        pct_change="% Change",
        avg_volume="Avg Daily Volume",
        best_day="Gain",
        worst_day="Loss",
    )
    # Step 5(e): format per semantic type -----------------------------------
    .fmt_number(columns=["open_px", "close_px"], decimals=2)
    .fmt_percent(columns="pct_change", decimals=1, accounting=True)
    .fmt_number(columns="avg_volume", decimals=2, scale_by=1e-9, pattern="{x}B")
    .fmt_percent(columns="best_day", decimals=2)
    .fmt_percent(columns="worst_day", decimals=2, accounting=True)
    # Step 3: Big Color — YlOrRd heat map on the monthly % change -----------
    .data_color(
        columns=COLOR_COLS,
        palette="YlOrRd",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 4: LIGHT heading band (Big Color present) ------------------------
    .tab_options(
        column_labels_background_color=WARM_TINT,
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): hairlines + row-group emphasis
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        row_group_background_color=GREY_BAND,
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # Step 5(c): striping (72 rows, body not fully filled)
        row_striping_background_color="#F6F6F6",
        # Frame
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    .opt_row_striping()
    # Step 5(d): stub tint (grey default keeps warm budget on the band)
    .tab_style(style=style.fill(color=GREY_BAND), locations=loc.stub())
    # Step 5(b): column-group vertical dividers at group seams
    .tab_style(style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
               locations=loc.body(columns=["close_px", "avg_volume"]))
    .tab_style(style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
               locations=loc.column_labels(columns=["close_px", "avg_volume"]))
    .cols_align(align="center", columns="pct_change")
    # Step 6: source notes -------------------------------------------------
    .tab_source_note(source_note=md(
        "**Single-day gain/loss** = the most extreme close-to-close daily return "
        "within the month. **% Change** = month-end close vs. month-open. "
        "Negatives shown in parentheses."))
    .tab_source_note(source_note="Source: S&P 500 daily prices (sp500.csv), 2010–2015.")
)

# ---- Step 7: render + verify ---------------------------------------------
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
print(monthly.head())
