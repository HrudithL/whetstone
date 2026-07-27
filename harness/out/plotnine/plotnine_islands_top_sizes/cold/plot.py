"""Rank the largest landmasses in islands.csv by area (horizontal bar)."""
import sys

import pandas as pd
from plotnine import aes, geom_col, ggplot, labs, coord_flip, scale_y_continuous, theme

sys.path.insert(
    0,
    ".claude/skills/plotnine/scripts",
)
from pn_house_style import apply_house_style, humanize_labels, save_plot, HOUSE_STYLE

# 1. UNDERSTAND THE DATA -----------------------------------------------------
# name (category), size (numeric area, thousands of sq miles). Already tidy.
df = pd.read_csv("islands.csv")
df["size"] = pd.to_numeric(df["size"], errors="coerce")
df = df.dropna(subset=["size"])

# Ranking: slice to the largest landmasses so the biggest are easy to compare.
TOP_N = 15
top = df.sort_values("size", ascending=False).head(TOP_N).copy()

# Sort bars by value (ascending so the largest lands on top after coord_flip).
order = top.sort_values("size", ascending=True)["name"].tolist()
top["name"] = pd.Categorical(top["name"], categories=order, ordered=True)

# 2/3/4. FORM, COLOR, LABELS -------------------------------------------------
lab = humanize_labels(
    "name", "size",
    overrides={"name": "Landmass", "size": "Area (thousands of sq mi)"},
)

p = (
    ggplot(top, aes(x="name", y="size"))
    + geom_col(fill=HOUSE_STYLE["accent"])  # single house accent -> no legend
    + coord_flip()
    + scale_y_continuous(labels=lambda v: [f"{x:,.0f}" for x in v])
    + labs(
        title=f"Top {TOP_N} by {lab['size']}",
        x=lab["name"],
        y=lab["size"],
    )
)

# 5. THEME (tall figure size is mandatory for a horizontal-bar ranking) ------
p = apply_house_style(p, legend_position="none")
p += theme(figure_size=(6, 7))  # tall size: mandatory for horizontal-bar ranking

# 6. RENDER ------------------------------------------------------------------
save_plot(p, "plot.png", width=6, height=7)
print("wrote plot.png")
