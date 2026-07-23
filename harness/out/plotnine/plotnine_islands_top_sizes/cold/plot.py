import pandas as pd
from plotnine import (
    ggplot, aes, geom_col, labs, coord_flip, theme_minimal, theme,
    element_text, element_line, element_blank
)

# Load data
df = pd.read_csv("islands.csv")

# Sort by size (descending) and set as ordered categorical for proper bar ordering
df = df.sort_values("size", ascending=True)  # ascending=True for horizontal bars
df["name"] = pd.Categorical(df["name"], categories=df["name"], ordered=True)

# Build plot
p = (
    ggplot(df, aes(x="name", y="size"))
    + geom_col(fill="#2C6FB3")
    + coord_flip()
    + labs(
        title="Largest Landmasses by Area",
        x="Landmass",
        y="Area (1000 square miles)"
    )
    + theme_minimal(base_size=12)
    + theme(
        plot_title=element_text(size=15, weight="bold", color="#222222"),
        axis_title=element_text(size=12, color="#222222"),
        axis_text=element_text(size=10, color="#222222"),
        panel_grid_major=element_line(color="#E6E6E6", size=0.4),
        panel_grid_minor=element_blank(),
        figure_size=(8, 5)
    )
)

# Render
p.save("plot.png", width=8, height=5, dpi=200, verbose=False)
print("Plot saved to plot.png")
