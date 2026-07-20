"""Top 10 most expensive GT cars, grouped by country of origin.

Story: a price ranking (MSRP is the hero measure) organized by the country the
car comes from, with each car's powertrain (drivetrain + transmission) shown
under one spanner.
"""
import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ── Step 1 · Understand + clean the data ────────────────────────────────────
df = pd.read_csv("gtcars.csv")

# One human-readable label per row; two separate mfr/model columns would force
# the reader to combine them mentally on every line.
df["car"] = df["mfr"] + " " + df["model"]

# The sort IS the message: top 10 by sticker price. Keep a stable 1-based
# overall rank so "top 10" stays legible after we regroup by country.
top = df.sort_values("msrp", ascending=False).head(10).reset_index(drop=True)
top["rank"] = top.index + 1

# Cluster the groups: order countries by their most expensive car, then order
# cars within each country by price — so groups are contiguous and the ranking
# still reads top-to-bottom.
country_order = (
    top.groupby("ctry_origin")["msrp"].max().sort_values(ascending=False).index
)
top["ctry_origin"] = pd.Categorical(top["ctry_origin"], country_order, ordered=True)
top = top.sort_values(["ctry_origin", "msrp"], ascending=[True, False])
top["ctry_origin"] = top["ctry_origin"].astype(str)

# Decode the terse codes into readable powertrain details.
drive_map = {"rwd": "RWD", "awd": "AWD", "fwd": "FWD"}
trsmn_map = {"7a": "7-spd auto", "8a": "8-spd auto", "8am": "8-spd auto-manual",
             "6a": "6-spd auto", "6m": "6-spd manual", "7m": "7-spd manual"}
top["drivetrain"] = top["drivetrain"].map(drive_map)
top["trsmn"] = top["trsmn"].map(trsmn_map)

top = top[["car", "ctry_origin", "rank", "msrp", "drivetrain", "trsmn"]]

# ── Step 3 · Big Color ──────────────────────────────────────────────────────
# One hero measure (MSRP): an ordered neutral magnitude over 10 rows → column
# gradient fill on Blues (palettes.md §3 — price is always Blues). Data-driven,
# backend-neutral domain across the whole column.
lo = float(np.nanmin(top[["msrp"]].to_numpy()))
hi = float(np.nanmax(top[["msrp"]].to_numpy()))

# ── Build the table ─────────────────────────────────────────────────────────
gt = (
    GT(top, rowname_col="car", groupname_col="ctry_origin")
    .tab_header(
        title="The World's Most Expensive GT Cars",
        subtitle="Top 10 by sticker price (MSRP), grouped by country of origin",
    )
    # Step 2 · organize columns + the Powertrain spanner (learned preference)
    .tab_stubhead(label="Car")
    .tab_spanner(label="Powertrain", columns=["drivetrain", "trsmn"])
    .cols_label(
        rank="Rank", msrp="MSRP", drivetrain="Drivetrain", trsmn="Transmission",
    )
    # Step 5(e) · format per semantic type
    .fmt_integer(columns=["rank"], use_seps=False)
    .fmt_currency(columns=["msrp"], currency="USD", decimals=0)
    .cols_align(align="center", columns=["rank", "drivetrain", "trsmn"])
    .cols_align(align="right", columns=["msrp"])
    # Step 3 · gradient fill on the hero measure
    .data_color(
        columns=["msrp"],
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # Step 4 · Big Color present → LIGHT band (washed-blue tint, dark bold text)
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a) · hairline between every body row
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # row-group emphasis: light fill + bold + structural rule
        row_group_background_color="#EAF0F6",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # Step 5(c) · row striping (10 rows; body not filled by Big Color)
        row_striping_background_color="#F6F6F6",
        # Frame · boxed enclosing border on all four sides
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    .opt_row_striping()
    # Step 5(d) · stub tint (grey — keeps the row labels distinct from the blue chrome)
    .tab_style(style=style.fill(color="#F0F0F0"), locations=loc.stub())
    .tab_style(style=style.text(weight="bold"), locations=loc.body(columns=["rank"]))
    # Step 5(b) · vertical divider at the Powertrain group boundary (body + header)
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="msrp"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="msrp"),
    )
    # Step 6 · source + methodology caption
    .tab_source_note(source_note=md("Source: **gtcars** dataset (Posit / great_tables sample data)."))
    .tab_source_note(source_note="Ranked by manufacturer's suggested retail price (MSRP); n = 10 cars.")
)

# ── Step 7 · Render + additional HTML artifact ──────────────────────────────
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
