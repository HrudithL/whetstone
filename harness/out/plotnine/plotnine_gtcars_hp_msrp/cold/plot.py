"""Price vs horsepower for the gtcars sports cars, colored by country of origin.

Flowchart decisions (plotnine skill):
1. DATA (data.md): one row per car already; coerce hp/msrp to numeric, drop rows that
   can't be positioned. Frame is already tidy -- no melt needed.
2. FORM (geoms.md): "relationship between two numeric vars" -> geom_point at the pinned
   HOUSE_STYLE["point_size"], plus a geom_smooth(method="lm") trend answering the same
   question (it recedes behind the points: thinner, neutral, dashed).
3. BIG COLOR (big_color.md): hero = ctry_origin, CATEGORICAL with 5 groups (<= ~6, so
   color rather than facets) -> qualitative Okabe-Ito via house_palette().
4. SCALES & LABELS (api.md, small_color.md #7): money axis gets a "$" + thousands
   separators; templated relationship title "{Y} vs {X}"; humanized axis labels + units.
5. SMALL COLOR (small_color.md): apply_house_style() -- theme_minimal, light major-only
   gridlines, pinned text sizes, legend right.
6. RENDER: save_plot() -> p.save("plot.png", ...), the only renderer.
"""
import sys
from pathlib import Path

import pandas as pd
from mizani.labels import label_currency
from plotnine import aes, geom_point, geom_smooth, ggplot, labs, scale_y_continuous

SKILL_SCRIPTS = (
    Path(__file__).resolve().parent / ".claude" / "skills" / "plotnine" / "scripts"
)
sys.path.insert(0, str(SKILL_SCRIPTS))
from pn_house_style import (  # noqa: E402
    HOUSE_STYLE,
    apply_house_style,
    house_palette,
    humanize_labels,
    save_plot,
)

# --- Step 1: data ----------------------------------------------------------------
df = pd.read_csv(Path(__file__).resolve().parent / "gtcars.csv")
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")
df = df.dropna(subset=["hp", "msrp", "ctry_origin"])

# --- Step 4 labels: humanize only what is VISIBLE (aes keeps raw column names) ----
lab = humanize_labels(
    "hp",
    "msrp",
    "ctry_origin",
    overrides={
        "hp": "Horsepower (hp)",
        "msrp": "MSRP (USD)",
        "ctry_origin": "Country of origin",
    },
)

# --- Steps 2-4: build ------------------------------------------------------------
p = (
    ggplot(df, aes("hp", "msrp", color="ctry_origin"))
    + geom_smooth(
        method="lm", se=False, color="#222222", size=0.6, linetype="dashed"
    )
    + geom_point(size=HOUSE_STYLE["point_size"], alpha=0.8)
    + house_palette("qualitative", aes="color", name=lab["ctry_origin"])
    + scale_y_continuous(
        labels=label_currency(prefix="$", precision=0, big_mark=",")
    )
    # title template (geoms.md): relationship -> "{Y} vs {X}"
    + labs(title=f"{lab['msrp']} vs {lab['hp']}", x=lab["hp"], y=lab["msrp"])
)

# --- Steps 5-6: theme + the mandatory renderer -----------------------------------
p = apply_house_style(p)
save_plot(p, str(Path(__file__).resolve().parent / "plot.png"))
