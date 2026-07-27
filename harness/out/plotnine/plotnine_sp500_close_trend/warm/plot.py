"""Trend of the S&P 500 closing price over the most recent year of data."""
import sys
from pathlib import Path

import pandas as pd
from mizani.labels import label_currency
from plotnine import (
    aes,
    geom_line,
    ggplot,
    labs,
    scale_x_date,
    scale_y_continuous,
)

# House style helper (single source of truth for theme/frame/mark sizes).
SKILL_SCRIPTS = Path(".claude/skills/plotnine/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
from pn_house_style import apply_house_style, humanize_labels, save_plot  # noqa: E402

# ---------------------------------------------------------------------------
# Step 1 — UNDERSTAND & CLEAN THE DATA -> one tidy, correctly-typed frame.
# ---------------------------------------------------------------------------
df = pd.read_csv("sp500.csv")
df["date"] = pd.to_datetime(df["date"])
df["close"] = pd.to_numeric(df["close"], errors="coerce")
df = df.dropna(subset=["date", "close"]).sort_values("date")

# Most recent year of data: the last 365 days up to the latest observation.
latest = df["date"].max()
recent = df[df["date"] >= latest - pd.Timedelta(days=365)].copy()

# Date span for the pinned date-axis defaults (api.md): ~1 year here
# -> > 90 days and <= 2 years -> "2 months" / "%b %Y".
lab = humanize_labels("date", "close", overrides={"close": "Closing Price (USD)",
                                                  "date": "Date"})

# ---------------------------------------------------------------------------
# Steps 2-4 — FORM (trend -> geom_line), BIG COLOR (single series, no hero
# variable -> constant accent, no legend; user prefers crimson + thicker line),
# SCALES & LABELS (currency y, pinned date breaks, templated title).
# ---------------------------------------------------------------------------
TREND_COLOR = "#D1495B"  # crimson (taught preference, overrides house accent)

p = (
    ggplot(recent, aes(x="date", y="close"))
    + geom_line(color=TREND_COLOR, size=1.5)
    + scale_x_date(date_breaks="2 months", date_labels="%b %Y")
    + scale_y_continuous(labels=label_currency(prefix="$", precision=0))
    + labs(
        title=f"{lab['close']} over time",
        x=lab["date"],
        y=lab["close"],
    )
)

# ---------------------------------------------------------------------------
# Step 5 — SMALL COLOR / THEME (no legend for a constant-color single series).
# ---------------------------------------------------------------------------
p = apply_house_style(p, legend_position="none")

# ---------------------------------------------------------------------------
# Step 6 — RENDER (the skill's only renderer).
# ---------------------------------------------------------------------------
save_plot(p, "plot.png")
print("wrote plot.png")
