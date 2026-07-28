"""Price vs horsepower for the gtcars sports cars, colored by country of origin.

Flowchart trace:
1. DATA (data.md)    -- 47 rows, one row per car: already tidy/long. Coerce hp/msrp to
                        numeric and drop rows that can't be positioned (none here).
2. FORM (geoms.md)   -- question = relationship between two numeric vars -> geom_point,
                        with a dashed lm overlay answering the same question.
3. BIG COLOR         -- hero = ctry_origin, a categorical (5 unordered groups) -> a
                        qualitative palette (ColorBrewer "Dark2", per user preference).
4. SCALES & LABELS   -- msrp is heavily right-skewed ($53.9k -> $1.42M), so the price
                        axis is log10 with $ thousands-separated ticks; templated title
                        "{Y} vs {X}".
5. SMALL COLOR       -- house theme via apply_house_style(), legend at the bottom.
6. RENDER            -- save_plot() -> p.save("plot.png", ...) at the house size/dpi.
"""
import sys
from pathlib import Path

import pandas as pd
from mizani.labels import label_currency
from plotnine import (
    aes,
    geom_point,
    geom_smooth,
    ggplot,
    labs,
    scale_color_brewer,
    scale_y_log10,
)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / ".claude" / "skills" / "plotnine" / "scripts"))
from pn_house_style import apply_house_style, humanize_labels, save_plot  # noqa: E402

# --- Step 1: one clean, correctly-typed, tidy DataFrame ----------------------
df = pd.read_csv(HERE / "gtcars.csv")
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")
df = df.dropna(subset=["hp", "msrp"])

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

# --- Steps 2-4: geom, Big Color, scales & labels ----------------------------
p = (
    ggplot(df, aes("hp", "msrp", color="ctry_origin"))
    + geom_point(size=3, alpha=0.6)  # taught: larger, translucent points
    + geom_smooth(method="lm", se=False, color="#222222", size=0.6, linetype="dashed")
    + scale_color_brewer(type="qual", palette="Dark2", name=lab["ctry_origin"])
    + scale_y_log10(labels=label_currency(prefix="$", precision=0, big_mark=","))
    # title template (geoms.md): relationship -> "{Y} vs {X}"
    + labs(title=f"{lab['msrp']} vs {lab['hp']}", x=lab["hp"], y=lab["msrp"])
)

# --- Step 5: Small Color / theme -------------------------------------------
p = apply_house_style(p, legend_position="bottom")

# --- Step 6: render (the only renderer) ------------------------------------
save_plot(p, str(HERE / "plot.png"))
