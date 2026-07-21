"""Heatmap / data-cell-styling archetype — distilled reference example.

Data: data/towny.csv  (414 Ontario municipalities; population and
      growth across five Census windows from 1996 to 2021)
Story: 25 years of growth in Ontario's 15 largest cities as a heatmap,
       with a diverging red→white→green palette centered at 0%.
"""
import pandas as pd
from great_tables import GT, html

df = pd.read_csv("data/towny.csv")

change_cols = [
    "pop_change_1996_2001_pct",
    "pop_change_2001_2006_pct",
    "pop_change_2006_2011_pct",
    "pop_change_2011_2016_pct",
    "pop_change_2016_2021_pct",
]
# Restrict to top 15 by 2021 population — heatmap patterns live in the
# reader's ability to scan a small grid; 414 rows is unreadable.
top = (
    df.nlargest(15, "population_2021")
      .loc[:, ["name", "population_2021"] + change_cols]
      .reset_index(drop=True)
)

# Symmetric ±|max| domain so 0% always maps to the white midpoint regardless
# of the data range. This is the correctness invariant for diverging color:
# without it, a column of all-positive values would map 0% to red.
abs_max = max(abs(top[change_cols].min().min()),
              abs(top[change_cols].max().max()))

(
    GT(top)
    .tab_header(
        title="Population growth in Ontario's 15 largest cities",
        subtitle="Five-year percent change across each Census window, 1996–2021",
    )
    .cols_label(
        name="City",
        population_2021="2021 pop.",
        pop_change_1996_2001_pct="1996–2001",
        pop_change_2001_2006_pct="2001–2006",
        pop_change_2006_2011_pct="2006–2011",
        pop_change_2011_2016_pct="2011–2016",
        pop_change_2016_2021_pct="2016–2021",
    )
    .tab_spanner(label="Inter-Census growth", columns=change_cols)
    .fmt_integer(columns=["population_2021"])
    # force_sign on the percent labels — the +/− gives a redundant directional
    # signal so the table remains usable for color-blind readers.
    .fmt_percent(columns=change_cols, decimals=1, force_sign=True)
    # RdYlGn diverging palette: red = decline, green = growth, white = no
    # change. Diverging (not sequential) because growth-rate is intrinsically
    # signed; a sequential ramp would conflate zero with one extreme.
    .data_color(
        columns=change_cols,
        palette=["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7",
                 "#d9f0d3", "#7fbf7b", "#1b7837"],
        domain=[-abs_max, abs_max],
    )
    .cols_align(align="left", columns=["name"])
    .cols_align(align="right", columns=["population_2021"] + change_cols)
    .tab_source_note(
        source_note=html(
            "Source: Statistics Canada Census of Population, 1996–2021, "
            "via the <code>towny</code> dataset (Posit / great_tables sample data). "
            "Color scale: red = decline, green = growth, midpoint at 0%."
        )
    )
)
