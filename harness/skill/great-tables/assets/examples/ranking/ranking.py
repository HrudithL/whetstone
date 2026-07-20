"""Ranking archetype — distilled reference example.

Data: data/gtcars.csv  (47 high-performance cars)
Story: Top 10 production cars by horsepower, with the leader visually
       called out.
"""
import pandas as pd
from great_tables import GT, loc, style

df = pd.read_csv("data/gtcars.csv")

# Compose a single human label per row. Two separate mfr/model columns force
# the reader to combine them mentally on every row.
df["car"] = df["mfr"] + " " + df["model"]

# Sort by hp descending and take the top 10. The sort IS the message; an
# unsorted dump erases the archetype.
top = df.sort_values("hp", ascending=False).head(10).reset_index(drop=True)
top["rank"] = top.index + 1  # 1-based; leaderboards start at #1, not #0.
top = top[["rank", "car", "year", "ctry_origin", "hp", "trq", "drivetrain", "msrp"]]

(
    GT(top)
    .tab_header(
        title="Top 10 by Horsepower",
        subtitle="Production cars in the gtcars dataset, ranked by peak HP",
    )
    .cols_label(
        rank="#", car="Car", year="Year", ctry_origin="Country",
        hp="HP", trq="Torque (lb-ft)", drivetrain="Drive", msrp="MSRP",
    )
    .fmt_currency(columns=["msrp"], currency="USD", decimals=0)
    .fmt_integer(columns=["hp", "trq"])
    # use_seps=False on year — `2,017` is wrong for a year.
    .fmt_integer(columns=["year"], use_seps=False)
    # Bold the rank column so the index pops, then highlight the leader row.
    .tab_style(style=style.text(weight="bold"), locations=loc.body(columns=["rank"]))
    .tab_style(style=style.fill(color="#fff4d6"), locations=loc.body(rows=[0]))
    .tab_style(style=style.text(weight="bold"), locations=loc.body(columns=["car", "hp"], rows=[0]))
    .cols_align(align="left", columns=["car", "ctry_origin", "drivetrain"])
    .cols_align(align="right", columns=["rank", "year", "hp", "trq", "msrp"])
    .tab_source_note(source_note="Source: gtcars dataset (Posit / great_tables sample data).")
)
