"""Chart the largest landmasses in islands.csv by area (top-N ranking)."""
import pandas as pd
from plotnine import (
    ggplot, aes, geom_col, coord_flip, labs, theme_classic, theme,
    element_line, element_text, element_blank, scale_y_continuous,
)

# --- Step 1: understand + tidy the data ------------------------------------
# Two columns: name (category) + size (area, thousands of square miles).
df = pd.read_csv("islands.csv")
df["size"] = pd.to_numeric(df["size"], errors="coerce")
df = df.dropna(subset=["size"])

# --- Step 2: choose the form -----------------------------------------------
# Ranking/amount across categories -> geom_col, horizontal (long labels),
# sliced to the top N so the biggest landmasses are easy to compare.
N = 15
top = df.sort_values("size", ascending=False).head(N)

# Sort so the largest ends up at the TOP after coord_flip().
order = top.sort_values("size", ascending=True)["name"].tolist()
top["name"] = pd.Categorical(top["name"], categories=order, ordered=True)

# --- Steps 3-4: single house accent (no hero color var), labels + units ----
HOUSE_ACCENT = "#2C6FB3"
Y_TITLE = "Area"  # humanized value label reused in the templated title
p = (
    ggplot(top, aes(x="name", y="size"))
    + geom_col(fill=HOUSE_ACCENT)
    + coord_flip()
    + scale_y_continuous(labels=lambda vs: [f"{v:,.0f}" for v in vs])
    + labs(
        title=f"Top {N} by {Y_TITLE}",
        x="Landmass",
        y="Area (thousands of sq mi)",
    )
)

# --- Step 5: Small Color / theme (L1: theme_classic base) ------------------
p = p + theme_classic(base_size=12) + theme(
    figure_size=(6, 7),  # mandatory TALL size for a horizontal-bar ranking
    plot_title=element_text(size=15, weight="bold", color="#222222"),
    axis_title=element_text(size=12, color="#222222"),
    axis_text=element_text(size=10, color="#222222"),
    panel_grid_major_x=element_line(color="#E6E6E6", size=0.4),
    panel_grid_minor=element_blank(),
    legend_position="none",
)

# --- Step 6: render (the only renderer) ------------------------------------
p.save("plot.png", width=6, height=7, dpi=200, verbose=False)
