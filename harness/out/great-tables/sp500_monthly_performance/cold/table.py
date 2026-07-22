"""S&P 500 monthly performance summary, 2010-2015.

Aggregates daily OHLCV data (sp500.csv) into one row per month, grouped by
year. Big Color: the monthly percent change is the hero signed measure and
gets a diverging RdYlGn fill (green = up, red = down) on a symmetric domain.
Rendered with Great Tables' gtsave to table.png, plus self-contained HTML.
"""
import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ---------------------------------------------------------------- Step 1: data
df = pd.read_csv("sp500.csv", parse_dates=["date"]).sort_values("date")
df = df[(df["date"].dt.year >= 2010) & (df["date"].dt.year <= 2015)].copy()

# Canonical single-day return = intraday (close - open) / open. Self-contained
# within each trading day, so the number reproduces exactly (stated in note).
df["daily_return"] = df["close"] / df["open"] - 1.0
df["ym"] = df["date"].dt.to_period("M")

# One row per month: opening = first trading day's open, closing = last trading
# day's close, avg daily volume, and the month's best/worst single-day return.
monthly = df.groupby("ym").agg(
    open=("open", "first"),
    close=("close", "last"),
    avg_volume=("volume", "mean"),
    best_day=("daily_return", "max"),
    worst_day=("daily_return", "min"),
).reset_index()

monthly["pct_change"] = monthly["close"] / monthly["open"] - 1.0
monthly["avg_vol_bn"] = monthly["avg_volume"] / 1e9          # billions of shares
monthly["year"] = monthly["ym"].dt.strftime("%Y")
monthly["month"] = monthly["ym"].dt.strftime("%b")

monthly = monthly[[
    "year", "month", "open", "close", "pct_change",
    "avg_vol_bn", "best_day", "worst_day",
]]

# ------------------------------------------------- Step 3: Big Color domain
# Hero = monthly percent change (signed). Symmetric, data-driven domain so 0
# sits at the palette midpoint. positive = good => RdYlGn (green = up).
M = float(np.nanmax(np.abs(monthly["pct_change"].to_numpy())))

# --------------------------------------------------------- Steps 2-6: build
gt = (
    GT(monthly, rowname_col="month", groupname_col="year")
    .tab_header(
        title="S&P 500 — Monthly Performance, 2010–2015",
        subtitle="Opening and closing levels, monthly return, average daily volume, and each month's largest single-day gain and loss",
    )
    .tab_spanner(label="Index Level (pts)", columns=["open", "close"])
    .tab_spanner(label="Largest Single-Day Move", columns=["best_day", "worst_day"])
    .cols_label(
        open="Open",
        close="Close",
        pct_change="Change",
        avg_vol_bn=md("Avg Daily Vol.<br>(bn shares)"),
        best_day="Gain",
        worst_day="Loss",
    )
    # Index levels are points, not dollars -> fmt_number (not fmt_currency).
    .fmt_number(columns=["open", "close"], decimals=2)
    .fmt_number(columns=["avg_vol_bn"], decimals=2)
    .fmt_percent(columns=["pct_change", "best_day", "worst_day"], decimals=2, force_sign=True)
    # Diverging fill on the hero measure only (one colored measure).
    .data_color(
        columns=["pct_change"],
        palette="RdYlGn",
        domain=[-M, M],
        truncate=False,
    )
    .cols_align(align="left", columns=["month"])
    .cols_align(align="right", columns=["open", "close", "pct_change", "avg_vol_bn", "best_day", "worst_day"])
    # ------------------------------------------------ Step 5: Small Color
    .opt_row_striping()
    .tab_style(style=style.fill(color="#F0F0F0"), locations=loc.stub())
    # column-group vertical dividers at each logical boundary (body + header)
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=[loc.body(columns=c) for c in ["close", "pct_change", "avg_vol_bn"]],
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=[loc.column_labels(columns=c) for c in ["close", "pct_change", "avg_vol_bn"]],
    )
    .tab_options(
        # cell hairlines
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        row_striping_background_color="#F6F6F6",
        # light heading band (Big Color present; diverging hue -> grey band)
        column_labels_background_color="#F0F0F0",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # row-group emphasis (fill + bold, required pair)
        row_group_background_color="#F0F0F0",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # Frame — boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    .tab_stubhead(label="Month")
    # ------------------------------------------------ Step 6: annotations
    .tab_source_note(
        source_note=md(
            "**Change** = month's closing level ÷ opening level − 1. "
            "**Gain / Loss** = largest and smallest single-day intraday return "
            "(daily close ÷ daily open − 1) within the month. Fill: green = up, red = down."
        )
    )
    .tab_source_note(source_note="Source: S&P 500 daily OHLCV data, 2010–2015.")
)

gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())
print("Wrote table.png and table.html")
