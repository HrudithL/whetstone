"""Price vs horsepower for the gtcars sports cars, as small multiples by country.

Flowchart trace (plotnine skill):
  1. DATA (data.md)      -- gtcars.csv is one row per car; coerce hp/msrp to numeric,
                            drop rows that can't be positioned. Already tidy (long).
  2. FORM (geoms.md)     -- "relationship between two numeric vars" -> geom_point,
                            size = HOUSE_STYLE["point_size"]. 47 points, so a light
                            alpha is enough for overplotting; no jitter/bin2d needed.
                            No geom_smooth: some panels hold only 2-4 cars, where an
                            lm fit would be a straight line through noise.
  3. BIG COLOR           -- country of origin is shown by FACETING, not by hue
                            (small multiples per panel), so no variable is
                            color-encoded: single house accent, no legend
                            (big_color.md, "No hero variable" section).
  4. SCALES & LABELS     -- MSRP is money -> label_currency; title from the
                            relationship template "{Y} vs {X}"; free y per panel so
                            narrow-range countries aren't flattened to a line.
  5. SMALL COLOR         -- apply_house_style(); legend suppressed; landscape figure
                            size (not a horizontal-bar ranking, so no tall branch).
  6. RENDER              -- save_plot() -> p.save("plot.png", ...).
"""
import sys
from pathlib import Path

import pandas as pd
from mizani.labels import label_currency
from plotnine import aes, element_text, facet_wrap, geom_point, ggplot, labs, scale_y_continuous, theme

SKILL_SCRIPTS = Path(".claude/skills/plotnine/scripts").resolve()
sys.path.insert(0, str(SKILL_SCRIPTS))
from pn_house_style import HOUSE_STYLE, apply_house_style, humanize_labels, save_plot

# --- Step 1: one clean, correctly-typed, tidy DataFrame -----------------------
df = pd.read_csv("gtcars.csv")
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")
df = df.dropna(subset=["hp", "msrp"])

# Panel order: most-represented country first (data-driven, not alphabetical).
country_order = df["ctry_origin"].value_counts().index.tolist()
df["ctry_origin"] = pd.Categorical(df["ctry_origin"], categories=country_order, ordered=True)

lab = humanize_labels(
    "hp", "msrp", "ctry_origin",
    overrides={"hp": "Horsepower", "msrp": "MSRP (USD)", "ctry_origin": "Country of Origin"},
)

# --- Steps 2-4: geom, accent color (no legend), scales, labels ---------------
p = (
    ggplot(df, aes("hp", "msrp"))
    + geom_point(color=HOUSE_STYLE["accent"], size=HOUSE_STYLE["point_size"], alpha=0.8)
    + facet_wrap("~ctry_origin", ncol=3, scales="free_y")
    + scale_y_continuous(labels=label_currency(prefix="$", precision=0, big_mark=","))
    # title template (geoms.md): relationship -> "{Y} vs {X}"
    + labs(
        title=f"{lab['msrp']} vs {lab['hp']}",
        subtitle=f"By {lab['ctry_origin'].lower()}; each panel keeps its own price range",
        x=lab["hp"],
        y=lab["msrp"],
    )
)

# --- Step 5: Small Color / theme ---------------------------------------------
p = apply_house_style(p, legend_position="none")
p = p + theme(
    # free_y gives every panel its own currency tick labels, so panels need room
    # between them (units are a FRACTION of the figure dimension, default 0.01)
    panel_spacing_x=0.10,
    panel_spacing_y=0.06,
    plot_subtitle=element_text(size=11, color=HOUSE_STYLE["text"]),
    strip_text=element_text(size=11, weight="bold", color=HOUSE_STYLE["text"]),
)

# --- Step 6: render -----------------------------------------------------------
save_plot(p, "plot.png")
