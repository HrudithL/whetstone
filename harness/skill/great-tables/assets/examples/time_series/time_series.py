"""Time-series archetype — distilled reference example.

Data: data/airquality.csv  (NYC daily air quality, May–Sep 1973)
Story: Monthly summary across the summer with inline sparkline of
       daily Ozone and a signed month-over-month delta.
"""
import pandas as pd
from great_tables import GT, html

df = pd.read_csv("data/airquality.csv")

# Map numeric Month codes to human labels so the reader does not have to
# translate "Month=7" → "July" mentally on every row.
month_name = {5: "May", 6: "June", 7: "July", 8: "August", 9: "September"}

monthly = df.groupby("Month").agg(
    ozone_mean=("Ozone", "mean"),
    temp_mean=("Temp", "mean"),
    wind_mean=("Wind", "mean"),
    solar_mean=("Solar_R", "mean"),
).reset_index()

# Pack daily Ozone into a space-separated string per month for fmt_nanoplot.
# Drop NaNs because nanoplot refuses missing values.
sparks = (
    df.dropna(subset=["Ozone"])
      .groupby("Month")["Ozone"]
      .apply(lambda s: " ".join(f"{v:.0f}" for v in s.tolist()))
      .reset_index()
      .rename(columns={"Ozone": "ozone_trend"})
)
monthly = monthly.merge(sparks, on="Month")
monthly["ozone_delta"] = monthly["ozone_mean"].diff()
monthly["month_label"] = monthly["Month"].map(month_name)
monthly = monthly[[
    "month_label", "ozone_mean", "ozone_delta", "ozone_trend",
    "temp_mean", "wind_mean", "solar_mean",
]]

(
    GT(monthly)
    .tab_header(
        title="NYC Air Quality — Summer 1973",
        subtitle="Monthly means and within-month ozone trend",
    )
    # Spanners group the four ozone columns and the three condition columns
    # so the reader parses the units block at a time.
    .tab_spanner(label="Ozone (ppb)", columns=["ozone_mean", "ozone_delta", "ozone_trend"])
    .tab_spanner(label="Conditions", columns=["temp_mean", "wind_mean", "solar_mean"])
    .cols_label(
        month_label="Month",
        ozone_mean="Mean",
        ozone_delta=html("&Delta; vs prev"),
        ozone_trend="Daily trend",
        temp_mean=html("Temp (&deg;F)"),
        wind_mean="Wind (mph)",
        solar_mean=html("Solar (W/m&sup2;)"),
    )
    # One decimal: half a ppb is below instrument resolution; more would be
    # spurious precision.
    .fmt_number(columns=["ozone_mean", "temp_mean", "wind_mean", "solar_mean"], decimals=1)
    .fmt_number(columns=["ozone_delta"], decimals=1, force_sign=True)
    # fmt_nanoplot draws an inline sparkline of the daily Ozone series in the
    # row — the trend belongs next to its summary, not in a side chart.
    .fmt_nanoplot(columns="ozone_trend", plot_type="line")
    .sub_missing(columns=["ozone_delta"], missing_text="—")
    .cols_align(align="left", columns=["month_label"])
    .tab_source_note(
        source_note="Source: New York State Department of Conservation, daily measurements May–September 1973."
    )
)
