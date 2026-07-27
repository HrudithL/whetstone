"""Trend of the S&P 500 closing price over the most recent year of data."""
import sys
from pathlib import Path

import pandas as pd
from plotnine import (
    aes,
    geom_line,
    ggplot,
    labs,
    scale_x_date,
    scale_y_continuous,
)
from mizani.labels import label_currency

# House style helper (theme, mark sizes, save) lives with the skill.
sys.path.insert(
    0,
    str(Path(".claude/skills/plotnine/scripts").resolve()),
)
from pn_house_style import HOUSE_STYLE, apply_house_style, humanize_labels, save_plot

# --- Step 1: understand & clean the data -> one tidy, correctly-typed frame ---
df = pd.read_csv("sp500.csv")
df["date"] = pd.to_datetime(df["date"])
df["close"] = pd.to_numeric(df["close"], errors="coerce")
df = df.dropna(subset=["date", "close"])

# Most recent year of data: last 365 days up to the latest observation.
latest = df["date"].max()
recent = df[df["date"] >= latest - pd.DateOffset(years=1)].sort_values("date")

# Span is ~1 year (>90 days and <=2 years) -> date_breaks "2 months", labels "%b %Y".

# --- Steps 2-4: single-series line, house accent (no hero color variable) ---
lab = humanize_labels("date", "close", overrides={"close": "Closing Price (USD)"})

p = (
    ggplot(recent, aes(x="date", y="close"))
    + geom_line(color=HOUSE_STYLE["accent"], size=HOUSE_STYLE["line_size"])
    + scale_x_date(date_breaks="2 months", date_labels="%b %Y")
    + scale_y_continuous(labels=label_currency(prefix="$", precision=0))
    + labs(
        title=f"{lab['close']} over time",
        x=lab["date"],
        y=lab["close"],
    )
)

# --- Step 5: house theme, no legend (single un-grouped series) ---
p = apply_house_style(p, legend_position="none")

# --- Step 6: render (the only renderer) ---
save_plot(p, "plot.png")
