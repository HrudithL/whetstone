"""S&P 500 monthly performance summary, 2010–2015 (great_tables)."""

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------------------
# Step 1 — UNDERSTAND & CLEAN THE DATA -> one correctly-typed DataFrame
# ---------------------------------------------------------------------------
# Daily OHLCV bars. Grain we want: one row per calendar month, 2010–2015.
raw = pd.read_csv("sp500.csv", parse_dates=["date"])
raw = raw[(raw["date"].dt.year >= 2010) & (raw["date"].dt.year <= 2015)]
raw = raw.sort_values("date")  # file is newest-first; make it chronological

# Canonical metric (F-canonical-metric): a "single-day gain/loss" is the daily
# intraday return = (close - open) / open, evaluated per trading day. Monthly
# "% change" = (month-end close - month-start open) / month-start open. Both
# stated in the source note so the numbers are reproducible.
raw["daily_ret"] = (raw["close"] - raw["open"]) / raw["open"]

g = raw.groupby([raw["date"].dt.year, raw["date"].dt.month])
tbl = pd.DataFrame({
    "year": [str(y) for (y, m) in g.groups],
    "month": [pd.Timestamp(2000, m, 1).strftime("%b") for (y, m) in g.groups],
    "open": g["open"].first().to_numpy(),
    "close": g["close"].last().to_numpy(),
    "avg_volume": g["volume"].mean().to_numpy(),
    "max_gain": g["daily_ret"].max().to_numpy(),
    "max_loss": g["daily_ret"].min().to_numpy(),
})
tbl["pct_change"] = (tbl["close"] - tbl["open"]) / tbl["open"]
tbl = tbl[["year", "month", "open", "close", "pct_change",
           "avg_volume", "max_gain", "max_loss"]]

# ---------------------------------------------------------------------------
# Step 3 — BIG COLOR: one colored measure = the hero, signed monthly % change.
# Diverging fill (RdYlGn, positive=good), symmetric data-driven domain.
# ---------------------------------------------------------------------------
M = float(np.nanmax(np.abs(tbl["pct_change"].to_numpy())))

# ---------------------------------------------------------------------------
# Steps 2 & 4–6 — build the table
# ---------------------------------------------------------------------------
gt = (
    GT(tbl, rowname_col="month", groupname_col="year")
    .tab_header(
        title="S&P 500 Monthly Performance",
        subtitle="Month-by-month summary of the index, 2010–2015",
    )
    .tab_stubhead(label="Month")
    # spanners (column groups)
    .tab_spanner(label="Price", columns=["open", "close"])
    .tab_spanner(label="Best / Worst Single Day", columns=["max_gain", "max_loss"])
    .cols_label(
        open="Open",
        close="Close",
        pct_change="% Change",
        avg_volume="Avg. Daily Volume",
        max_gain="Best Day",
        max_loss="Worst Day",
    )
    # Step 5(e) — formatting per column.
    # Currency for the price columns (US dollars); accounting-style negatives
    # (parentheses) for every signed number.
    .fmt_currency(columns=["open", "close"], currency="USD",
                  decimals=2, accounting=True)
    .fmt_percent(columns=["pct_change", "max_gain", "max_loss"],
                 decimals=2, accounting=True)
    .fmt_number(columns="avg_volume", compact=True, decimals=2)
    # Step 3 — diverging fill on the hero
    .data_color(
        columns="pct_change",
        palette="RdYlGn",
        domain=[-M, M],
        truncate=False,
    )
    # Step 5(a) — cell hairlines + column-label bottom rule
    .tab_options(
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 4 — LIGHT band (Big Color present); diverging has no DA hue -> grey
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        # Step 5 sub-note — row-group emphasis (fill + bold)
        row_group_background_color="#F0F0F0",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # Step 5(c) — striping
        row_striping_background_color="#F6F6F6",
    )
    .opt_row_striping()
    # Step 5(d) — stub tint
    .tab_style(style=style.fill(color="#F0F0F0"), locations=loc.stub())
    # Step 5(b) — vertical dividers at each column-group boundary
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=[loc.body(columns=c) for c in ["close", "pct_change", "avg_volume"]],
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=[loc.column_labels(columns=c) for c in ["close", "pct_change", "avg_volume"]],
    )
    # Step 6 — titles/annotations
    .tab_source_note(source_note=md(
        "**Single-day gain/loss** = daily intraday return "
        "(close − open) ÷ open. **% Change** = (month-end close − "
        "month-start open) ÷ month-start open. Negatives shown in "
        "accounting style; volume in shares."
    ))
    .tab_source_note(source_note="Source: S&P 500 daily OHLCV, 2010–2015.")
    # Frame — boxed enclosing border on all four sides
    .tab_options(
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
)

# ---------------------------------------------------------------------------
# Step 7 — RENDER
# ---------------------------------------------------------------------------
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())
print("wrote table.png and table.html")
