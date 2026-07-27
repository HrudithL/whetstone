"""Line archetype: a trend over time (single series).

Question -> geom (geoms.md): "trend over time" -> geom_line. x must be real
datetimes (data.md). Big Color: single series, nothing to group -> house accent,
no legend (big_color.md). Date axis + thousands y ticks (small_color.md/api.md).
"""
import sys
from pathlib import Path

import pandas as pd
from plotnine import ggplot, aes, geom_line, labs, scale_x_date, scale_y_continuous
from mizani.labels import label_comma

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pn_house_style import HOUSE_STYLE, apply_house_style, save_plot

df = pd.read_csv(Path(__file__).resolve().parents[6] / "data" / "sp500.csv")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")
# keep it readable: one recent year
df = df[df["date"] >= df["date"].max() - pd.Timedelta(days=365)]

p = (
    ggplot(df, aes("date", "close"))
    + geom_line(color=HOUSE_STYLE["accent"], size=HOUSE_STYLE["line_size"])
    # date-axis defaults (api.md): ~365-day span falls in the "90 days-2 years" bucket
    + scale_x_date(date_breaks="2 months", date_labels="%b %Y")
    + scale_y_continuous(labels=label_comma())
    # title template (geoms.md): trend over time, no color-encoded group -> "{Y} over time"
    + labs(title="Close over time",
           x="", y="Close")
)
p = apply_house_style(p, legend_position="none")
save_plot(p, str(Path(__file__).with_name("line.png")))
