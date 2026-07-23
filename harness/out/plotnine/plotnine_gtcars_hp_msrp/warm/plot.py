import pandas as pd
from plotnine import (
    ggplot, aes, geom_point, labs, theme_minimal, theme,
    element_text, element_line, element_blank,
    scale_color_manual, scale_y_log10
)

# STEP 1: Load and clean data
df = pd.read_csv("gtcars.csv")

# Ensure numeric types
df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")

# Remove rows with missing hp or msrp
df = df.dropna(subset=["hp", "msrp"])

# STEP 2 & 3: Build the plot with geom_point and color encoding for country
# Okabe-Ito qualitative palette from big_color.md
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]

p = (
    ggplot(df, aes("hp", "msrp", color="ctry_origin"))
    # STEP 2: Scatter plot for relationship
    + geom_point(size=2.5, alpha=0.7)
    # STEP 3: Color by country (categorical)
    + scale_color_manual(values=OKABE_ITO, name="Country")
    # STEP 4: Log scale for price (user preference) + labels with units
    + scale_y_log10(name="Price (USD, log scale)")
    + labs(
        title="Sports Car Price vs. Horsepower",
        x="Horsepower (hp)",
        y="Price (USD, log scale)"
    )
    # STEP 5: Theme and styling
    + theme_minimal(base_size=12)
    + theme(
        figure_size=(8, 5),
        plot_title=element_text(size=15, weight="bold", color="#222222"),
        axis_title=element_text(size=12, color="#222222"),
        axis_text=element_text(size=10, color="#222222"),
        panel_grid_major=element_line(color="#E6E6E6", size=0.4),
        panel_grid_minor=element_blank(),
        legend_title=element_text(size=11, color="#222222"),
        legend_text=element_text(size=10, color="#222222"),
        legend_position="right"
    )
)

# STEP 6: Render and save
p.save("plot.png", width=8, height=5, dpi=200, verbose=False)
print("Plot saved to plot.png")
