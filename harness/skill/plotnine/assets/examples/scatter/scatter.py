"""Scatter archetype: relationship between two numeric variables, grouped.

Question -> geom (geoms.md): "relationship between two numeric vars" -> geom_point.
Big Color (big_color.md): hero = country of origin, a CATEGORICAL var -> qualitative
Okabe-Ito palette. Small Color + save via the house helpers.
"""
import sys
from pathlib import Path

import pandas as pd
from plotnine import ggplot, aes, geom_point, geom_smooth, labs

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pn_house_style import apply_house_style, house_palette, humanize_labels, save_plot

df = pd.read_csv(Path(__file__).resolve().parents[6] / "data" / "gtcars.csv")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df = df.dropna(subset=["hp", "msrp"])

lab = humanize_labels("hp", "msrp", "ctry_origin",
                      overrides={"msrp": "MSRP (USD)", "hp": "Horsepower",
                                 "ctry_origin": "Origin"})
p = (
    ggplot(df, aes("hp", "msrp", color="ctry_origin"))
    + geom_point(size=2.5, alpha=0.8)
    + geom_smooth(method="lm", se=False, color="#222222", size=0.6, linetype="dashed")
    + house_palette("qualitative", aes="color", name=lab["ctry_origin"])
    + labs(title="Price rises with horsepower across origins",
           x=lab["hp"], y=lab["msrp"])
)
p = apply_house_style(p)
save_plot(p, str(Path(__file__).with_name("scatter.png")))
