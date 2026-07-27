"""Price vs horsepower for the gtcars sports cars, colored by country of origin."""
import os
import sys

import pandas as pd
from mizani.labels import label_comma, label_currency
from plotnine import aes, geom_point, ggplot, labs, scale_x_continuous, scale_y_continuous

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                ".claude", "skills", "plotnine", "scripts"))
from pn_house_style import (  # noqa: E402
    HOUSE_STYLE,
    apply_house_style,
    house_palette,
    humanize_labels,
    save_plot,
)

# ---- Step 1: understand & clean the data -> one tidy, correctly-typed frame ----
df = pd.read_csv("gtcars.csv")
df = df[["hp", "msrp", "ctry_origin"]].dropna()
df["hp"] = df["hp"].astype(float)
df["msrp"] = df["msrp"].astype(float)
df["ctry_origin"] = df["ctry_origin"].astype("category")

# ---- Step 4: humanized labels (units where the data has them) ----
lab = humanize_labels(
    "hp", "msrp", "ctry_origin",
    overrides={
        "hp": "Horsepower (hp)",
        "msrp": "Price (USD)",
        "ctry_origin": "Country of Origin",
    },
)

# ---- Steps 2 & 3: relationship -> geom_point; hero categorical var -> qualitative ----
p = (
    ggplot(df, aes(x="hp", y="msrp", color="ctry_origin"))
    + geom_point(size=HOUSE_STYLE["point_size"], alpha=0.85)
    + house_palette("qualitative", aes="color", name=lab["ctry_origin"])
    + scale_x_continuous(labels=label_comma())
    + scale_y_continuous(labels=label_currency(prefix="$", precision=0))
    + labs(
        title=f"{lab['msrp']} vs {lab['hp']}",
        x=lab["hp"],
        y=lab["msrp"],
    )
)

# ---- Step 5: house theme ----
p = apply_house_style(p)

# ---- Step 6: render (the skill's mandatory renderer) ----
save_plot(p, "plot.png")
print("wrote plot.png")
