"""Plot how price (MSRP) relates to horsepower for the gtcars sports cars,
colored by country of origin. Built with plotnine following the house style.
"""
import sys
from pathlib import Path

import pandas as pd
from plotnine import ggplot, aes, geom_point, labs, scale_y_log10
from mizani.labels import label_currency

# House style helpers live in the skill's scripts/ directory.
SKILL_SCRIPTS = Path(
    ".claude/skills/plotnine/scripts"
).resolve()
sys.path.insert(0, str(SKILL_SCRIPTS))
from pn_house_style import apply_house_style, house_palette, humanize_labels, save_plot, HOUSE_STYLE

# --- Step 1: understand + clean the data --------------------------------------
df = pd.read_csv("gtcars.csv")
# hp and msrp are already numeric floats; ctry_origin is the categorical hero.
df = df.dropna(subset=["hp", "msrp", "ctry_origin"])

# --- Step 4: humanized labels -------------------------------------------------
lab = humanize_labels(
    "hp", "msrp", "ctry_origin",
    overrides={"hp": "Horsepower (hp)", "msrp": "MSRP (USD)", "ctry_origin": "Country of Origin"},
)

# --- Steps 2, 3, 4: scatter, categorical Big Color, scales --------------------
p = (
    ggplot(df, aes(x="hp", y="msrp", color="ctry_origin"))
    + geom_point(size=HOUSE_STYLE["point_size"], alpha=0.85)
    + scale_y_log10(labels=label_currency(prefix="$", precision=0))  # price on a log scale
    + house_palette("qualitative", aes="color", name=lab["ctry_origin"])
    + labs(
        title=f"{lab['msrp']} vs {lab['hp']}",
        x=lab["hp"],
        y=lab["msrp"],
        color=lab["ctry_origin"],
    )
)

# --- Step 5: house theme ------------------------------------------------------
p = apply_house_style(p)

# --- Step 6: render -----------------------------------------------------------
save_plot(p, "plot.png")
print("wrote plot.png")
