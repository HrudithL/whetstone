"""Price vs horsepower for the gtcars sports cars, colored by country of origin.

Step 1 (data.md):     47 rows, one row per car; hp / msrp already numeric, no NaNs.
Step 2 (geoms.md):    relationship between two numeric vars -> geom_point, pinned point_size,
                      + a single overall geom_smooth(method="lm") trend.
Step 3 (big_color.md): hero = ctry_origin, CATEGORICAL (5 groups, <= 6) -> qualitative
                      Okabe-Ito palette via house_palette(); color, not facets.
Step 4:               price spans $53.9k -> $1.42M (26x, one extreme LaFerrari), so the
                      y axis is log10 -- on a linear axis 46 of 47 cars pile into the
                      bottom third and the linear fit dips below $0. $ tick labels with
                      thousands separators; templated title "{Y} vs {X}".
Step 5/6 (small_color.md): house theme + save_plot() at the house size/dpi.
"""
import sys
from pathlib import Path

import pandas as pd
from mizani.labels import label_currency
from plotnine import aes, geom_point, geom_smooth, ggplot, labs, scale_y_continuous

SKILL = Path(".claude/skills/plotnine").resolve()
sys.path.insert(0, str(SKILL / "scripts"))
from pn_house_style import (  # noqa: E402
    HOUSE_STYLE,
    apply_house_style,
    house_palette,
    humanize_labels,
    save_plot,
)

# --- Step 1: one clean, correctly-typed, tidy frame -------------------------
df = pd.read_csv("gtcars.csv")
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")
df = df.dropna(subset=["hp", "msrp", "ctry_origin"])

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

# --- Steps 2-4: form, Big Color, scales & labels ----------------------------
p = (
    ggplot(df, aes("hp", "msrp", color="ctry_origin"))
    # group=1 keeps this one overall trend line, not one per color group
    + geom_smooth(
        aes(group=1), method="lm", se=False,
        color="#222222", size=0.6, linetype="dashed",
    )
    + geom_point(size=HOUSE_STYLE["point_size"], alpha=0.8)
    + house_palette("qualitative", aes="color", name=lab["ctry_origin"])
    + scale_y_continuous(
        trans="log10",
        breaks=[50_000, 100_000, 200_000, 400_000, 800_000, 1_600_000],
        labels=label_currency(prefix="$", precision=0, big_mark=","),
    )
    # title template (geoms.md, relationship): "{Y} vs {X}"
    + labs(
        title=f"{lab['msrp']} vs {lab['hp']}",
        subtitle="Each point is one model; dashed line is the overall log-linear fit",
        x=lab["hp"],
        y=f"{lab['msrp']}, log scale",
    )
)

# --- Steps 5-6: house theme, then the mandatory renderer --------------------
p = apply_house_style(p)
save_plot(p, "plot.png")
