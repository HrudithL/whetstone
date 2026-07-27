"""Bar archetype: ranking / amount across categories (pre-aggregated).

Question -> geom (geoms.md): "ranking/amount across categories" -> geom_col
(stat="identity"), sorted by value, horizontal because labels are long.
Big Color: nothing worth color-encoding -> single house accent, no legend
(big_color.md). Small Color + save via the house helpers.
"""
import sys
from pathlib import Path

import pandas as pd
from plotnine import ggplot, aes, geom_col, coord_flip, labs

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pn_house_style import HOUSE_STYLE, apply_house_style, humanize_labels, save_plot

df = pd.read_csv(Path(__file__).resolve().parents[6] / "data" / "islands.csv")
top = df.sort_values("size", ascending=False).head(12)
# order categorical ascending so the biggest bar is at the TOP after coord_flip
order = top.sort_values("size", ascending=True)["name"].tolist()
top["name"] = pd.Categorical(top["name"], categories=order, ordered=True)

lab = humanize_labels("size", overrides={"size": "Area (thousand sq mi)"})
# title template (geoms.md): ranking, sliced to a top-N -> "Top {n} by {Y}"
p = (
    ggplot(top, aes("name", "size"))
    + geom_col(fill=HOUSE_STYLE["accent"], width=0.75)
    + coord_flip()
    + labs(title=f"Top {len(top)} by {lab['size']}", x="", y=lab["size"])
)
p = apply_house_style(p, legend_position="none")
# HARD BRANCH (SKILL.md Global constants): horizontal/coord_flip ranking -> (6, 7),
# never the (8, 5) default.
save_plot(p, str(Path(__file__).with_name("bar.png")), height=7, width=6)
