import pandas as pd
from plotnine import (
    ggplot, aes, geom_col, labs, theme_classic, coord_flip,
    theme, element_text, element_line, element_blank
)

# Step 1: Load and prepare data
df = pd.read_csv("islands.csv")

# Sort by size (ascending so largest appears at top after coord_flip)
df = df.sort_values("size", ascending=True)

# Convert name to ordered categorical to preserve sort order
df["name"] = pd.Categorical(df["name"], categories=df["name"], ordered=True)

# Step 2: Create the plot with geom_col (ranking/amount)
p = (
    ggplot(df, aes(x="name", y="size"))
    + geom_col(fill="#2C6FB3")  # House accent, no legend
    + coord_flip()  # Horizontal bars for better label readability

    # Step 4: Labels and axes
    + labs(
        title="Largest Landmasses by Area",
        x="Island/Continent",
        y="Area (thousands of km²)"
    )

    # Step 5: Theme and polish (using theme_classic per user preference L1)
    + theme_classic(base_size=12)
    + theme(
        # Text hierarchy
        plot_title=element_text(size=15, weight="bold"),
        axis_title=element_text(size=12, color="#222222"),
        axis_text=element_text(size=10, color="#222222"),
        # Gridlines
        panel_grid_major=element_line(color="#E6E6E6", size=0.4),
        panel_grid_minor=element_blank(),
        # Panel background
        plot_background=element_blank(),
        panel_background=element_blank(),
    )
)

# Step 6: Render and save
p.save("plot.png", width=6, height=7, dpi=200, verbose=False)
print("Plot saved to plot.png")
