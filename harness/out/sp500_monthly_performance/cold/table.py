"""S&P 500 monthly performance summary, 2010-2015, rendered with great_tables."""
import calendar

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------------------
# Step 1 - clean, correctly-typed data + monthly aggregation
# ---------------------------------------------------------------------------
raw = pd.read_csv("sp500.csv", parse_dates=["date"])
raw = raw.sort_values("date").reset_index(drop=True)

# Canonical single-day return = close-to-close daily percent change, computed on
# the full daily series so a month's first trading day uses the prior day's close.
raw["daily_ret"] = raw["close"].pct_change()
raw["year"] = raw["date"].dt.year
raw["month"] = raw["date"].dt.month

window = raw[raw["year"].between(2010, 2015)].copy()

records = []
for (yr, mo), sub in window.groupby(["year", "month"]):
    sub = sub.sort_values("date")
    open_p = sub["open"].iloc[0]           # first trading day's open
    close_p = sub["close"].iloc[-1]        # last trading day's close
    records.append(
        {
            "year": yr,
            "month": calendar.month_name[mo],
            "open_price": open_p,
            "close_price": close_p,
            "pct_change": (close_p - open_p) / open_p,      # fractional
            "avg_volume": sub["volume"].mean(),
            "best_day": sub["daily_ret"].max(),             # largest single-day gain
            "worst_day": sub["daily_ret"].min(),            # largest single-day loss
        }
    )

df = pd.DataFrame.from_records(records)

# ---------------------------------------------------------------------------
# Step 3 - Big Color: monthly % change is the signed hero -> diverging RdYlGn
# ---------------------------------------------------------------------------
lo = float(np.nanmin(df["pct_change"]))
hi = float(np.nanmax(df["pct_change"]))
M = max(abs(lo), abs(hi))                                    # symmetric domain

# ---------------------------------------------------------------------------
# Steps 2, 4, 5, 6 - build the table
# ---------------------------------------------------------------------------
gt = (
    GT(df, rowname_col="month", groupname_col="year")
    .tab_header(
        title="S&P 500 Monthly Performance",
        subtitle=md(
            "Opening & closing price, monthly return, average daily volume, and "
            "single-day extremes for every month, 2010&ndash;2015"
        ),
    )
    .tab_stubhead(label="Month")
    # --- spanners (Step 2) ---
    .tab_spanner(label="Monthly Price", columns=["open_price", "close_price"])
    .tab_spanner(label="Single-Day Return", columns=["best_day", "worst_day"])
    .cols_label(
        open_price="Open",
        close_price="Close",
        pct_change="% Change",
        avg_volume="Avg. Daily Volume",
        best_day="Best Day",
        worst_day="Worst Day",
    )
    # --- formatting per column (Step 5e) ---
    .fmt_number(columns=["open_price", "close_price"], decimals=2)
    .fmt_percent(columns="pct_change", decimals=1, force_sign=True)
    .fmt_number(columns="avg_volume", compact=True, decimals=2)
    .fmt_percent(columns=["best_day", "worst_day"], decimals=1, force_sign=True)
    .sub_missing(missing_text="—")
    # --- Big Color: diverging fill on the hero (Step 3) ---
    .data_color(
        columns="pct_change",
        palette="RdYlGn",
        domain=[-M, M],
        truncate=False,
    )
    # --- heading band: Big Color present -> LIGHT grey band (Step 4) ---
    .tab_options(
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # cell hairlines (Step 5a)
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # row-group emphasis (Step 5 sub-note)
        row_group_background_color="#F0F0F0",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # row striping (Step 5c: 72 rows, body not fully filled)
        row_striping_background_color="#F6F6F6",
        # frame (global constant)
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    .opt_row_striping()
    # stub tint (Step 5d)
    .tab_style(style=style.fill(color="#F0F0F0"), locations=loc.stub())
    # column-group vertical dividers at group boundaries (Step 5b)
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=[
            loc.body(columns=["close_price", "pct_change", "avg_volume"]),
            loc.column_labels(columns=["close_price", "pct_change", "avg_volume"]),
        ],
    )
    # --- source notes (Step 6) ---
    .tab_source_note(
        source_note=md(
            "**Source:** S&P 500 daily OHLCV data (`sp500.csv`)."
        )
    )
    .tab_source_note(
        source_note=md(
            "*% Change* = (last trading day's close &minus; first trading day's open) &divide; "
            "first open. *Best / Worst Day* = the largest and smallest single-day "
            "close-to-close return within the month."
        )
    )
)

gt.gtsave("table.png", expand=15, vwidth=1200, vheight=2900)

with open("table.html", "w") as fh:
    fh.write(gt.as_raw_html())

print("wrote table.png and table.html")
