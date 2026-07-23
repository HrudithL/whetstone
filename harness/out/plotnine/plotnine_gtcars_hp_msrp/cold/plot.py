import pandas as pd
from plotnine import (
    ggplot, aes, geom_point, labs, theme_minimal, theme,
    scale_color_manual, scale_y_continuous, element_text, element_line, element_blank
)
from mizani.labels import label_currency

# Read the data
df = pd.read_csv("gtcars.csv")

# Drop rows with missing hp or msrp
df = df.dropna(subset=["hp", "msrp", "ctry_origin"])

# Define the Okabe-Ito qualitative palette
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]

# Create the plot
p = (
    ggplot(df, aes(x="hp", y="msrp", color="ctry_origin"))
    + geom_point(alpha=0.7, size=3)
    + scale_color_manual(values=OKABE_ITO, name="Country of Origin")
    + labs(
        title="Sports Car Price vs Horsepower by Country of Origin",
        x="Horsepower (hp)",
        y="Price (USD)",
    )
    + theme_minimal(base_size=12)
    + theme(
        plot_title=element_text(size=15, weight="bold", color="#222222"),
        axis_title=element_text(size=12, color="#222222"),
        axis_text=element_text(size=10, color="#222222"),
        panel_grid_major=element_line(color="#E6E6E6", size=0.4),
        panel_grid_minor=element_blank(),
        legend_position="right",
    )
)

# Format y-axis as currency
p = p + scale_y_continuous(labels=label_currency(prefix="$", precision=0))

# Save the plot
p.save("plot.png", width=8, height=5, dpi=200, verbose=False)

print("Plot saved to plot.png")
