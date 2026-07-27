"""Scatter of price (MSRP) vs horsepower for the gtcars sports cars,
colored by country of origin. Built with plotnine, rendered to plot.png.
"""
import sys
from pathlib import Path

import pandas as pd
from mizani.formatters import currency_format, comma_format
from plotnine import (
    ggplot,
    aes,
    geom_point,
    labs,
    scale_x_continuous,
    scale_y_continuous,
)

# House-style helpers live alongside the skill.
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent
        / ".claude/skills/plotnine/scripts"
    ),
)
from pn_house_style import (  # noqa: E402
    apply_house_style,
    house_palette,
    humanize_labels,
    save_plot,
    HOUSE_STYLE,
)

# --- Step 1: understand + clean the data -----------------------------------
df = pd.read_csv("gtcars.csv")
# hp, msrp read as floats already; ctry_origin is a clean categorical string.
df = df.dropna(subset=["hp", "msrp", "ctry_origin"])

# --- Step 4: labels (humanized, with units) --------------------------------
lab = humanize_labels(
    "hp",
    "msrp",
    "ctry_origin",
    overrides={
        "hp": "Horsepower (hp)",
        "msrp": "Price (MSRP, USD)",
        "ctry_origin": "Country of origin",
    },
)

# --- Steps 2, 3 & 5: geom, Big Color, scales, theme ------------------------
p = (
    ggplot(df, aes(x="hp", y="msrp", color="ctry_origin"))
    + geom_point(size=HOUSE_STYLE["point_size"])
    + house_palette("qualitative", aes="color", name=lab["ctry_origin"])
    + scale_x_continuous(labels=comma_format())
    + scale_y_continuous(labels=currency_format(precision=0, big_mark=","))
    + labs(
        title=f"{lab['msrp']} vs {lab['hp']}",
        x=lab["hp"],
        y=lab["msrp"],
    )
)
p = apply_house_style(p)

# --- Step 6: render ---------------------------------------------------------
save_plot(p, "plot.png")
print("wrote plot.png")
