"""Distribution archetype: compare a numeric distribution across groups.

Question -> geom (geoms.md): "compare distributions across groups" -> geom_boxplot,
group on x. Big Color: the grouping (month) is the hero CATEGORICAL -> qualitative
fill (big_color.md). Ordered categorical so months sort correctly (data.md).
"""
import sys
from pathlib import Path

import pandas as pd
from plotnine import ggplot, aes, geom_boxplot, labs

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pn_house_style import apply_house_style, house_palette, save_plot

df = pd.read_csv(Path(__file__).resolve().parents[6] / "data" / "airquality.csv")
df = df.dropna(subset=["Temp"])
names = {5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep"}
df["Month"] = pd.Categorical(df["Month"].map(names),
                             categories=list(names.values()), ordered=True)

p = (
    ggplot(df, aes("Month", "Temp", fill="Month"))
    + geom_boxplot(alpha=0.85, outlier_alpha=0.4)
    + house_palette("qualitative", aes="fill", name="Month")
    + labs(title="Temperature distribution by month",
           x="", y="Temperature (°F)")
)
p = apply_house_style(p, legend_position="none")  # x already labels the groups
save_plot(p, str(Path(__file__).with_name("distribution.png")))
