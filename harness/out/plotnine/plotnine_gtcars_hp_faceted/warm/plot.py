"""Price vs. horsepower for sports cars, faceted by country of origin."""
import sys
from pathlib import Path

import pandas as pd
from mizani.formatters import currency_format
from plotnine import (
    aes,
    facet_wrap,
    geom_point,
    ggplot,
    labs,
    scale_y_continuous,
)

sys.path.insert(0, str(Path(__file__).parent / ".claude/skills/plotnine/scripts"))
from pn_house_style import HOUSE_STYLE, apply_house_style, humanize_labels, save_plot

# --- Step 1: one clean, correctly-typed, tidy DataFrame -----------------------
df = pd.read_csv("gtcars.csv")
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")
df = df.dropna(subset=["hp", "msrp", "ctry_origin"])

# --- Steps 2-4: relationship scatter, faceted by country (no color encoding) --
lab = humanize_labels(
    "hp", "msrp", overrides={"hp": "Horsepower", "msrp": "MSRP (USD)"}
)

p = (
    ggplot(df, aes(x="hp", y="msrp"))
    + geom_point(color=HOUSE_STYLE["accent"], size=HOUSE_STYLE["point_size"], alpha=0.8)
    + facet_wrap("~ctry_origin")
    + scale_y_continuous(labels=currency_format(prefix="$", big_mark=",", accuracy=1))
    + labs(
        title=f"{lab['msrp']} vs {lab['hp']}",
        subtitle="Sports cars, by country of origin",
        x=lab["hp"],
        y=lab["msrp"],
    )
)

# --- Step 5: house theme; no legend (no variable is color-encoded) ------------
p = apply_house_style(p, legend_position="none")

# --- Step 6: render ----------------------------------------------------------
save_plot(p, "plot.png")
print("wrote plot.png")
