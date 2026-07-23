import pandas as pd
from plotnine import (
    ggplot, aes, geom_line, labs, theme_minimal,
    theme, element_text, element_line, element_blank,
    scale_x_date, scale_y_continuous
)
from mizani.labels import label_comma

# Load data
df = pd.read_csv("sp500.csv")

# Parse date to datetime
df["date"] = pd.to_datetime(df["date"])

# Filter to most recent year of data
max_date = df["date"].max()
one_year_ago = max_date - pd.Timedelta(days=365)
df_recent = df[df["date"] >= one_year_ago].copy()

# Build plot
p = (
    ggplot(df_recent, aes(x="date", y="close"))
    + geom_line(color="#2C6FB3", size=0.8)
    + labs(
        title="S&P 500 Closing Price Trend",
        x="Date",
        y="Closing Price ($)"
    )
    + scale_x_date(date_labels="%b %Y", date_breaks="1 month")
    + scale_y_continuous(labels=label_comma())
    + theme_minimal(base_size=12)
    + theme(
        figure_size=(8, 5),
        plot_title=element_text(size=15, weight="bold", color="#222222"),
        axis_title=element_text(size=12, color="#222222"),
        axis_text=element_text(size=10, color="#222222"),
        panel_grid_major=element_line(color="#E6E6E6", size=0.4),
        panel_grid_minor=element_blank(),
        axis_line=element_line(color="#E6E6E6", size=0.4)
    )
)

# Render
p.save("plot.png", width=8, height=5, dpi=200, verbose=False)
print("Plot saved to plot.png")
