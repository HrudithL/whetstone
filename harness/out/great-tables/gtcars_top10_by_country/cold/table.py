"""Top 10 most expensive GT cars, grouped by country of origin.

Flowchart trace
  1 UNDERSTAND  one car per row; hero measure = MSRP (neutral price magnitude);
                categories = country (grouping), drivetrain, transmission.
  2 ORGANIZE    stub = car name; groupname_col = country (prompt says "grouped by");
                keep MSRP + decoded drivetrain + decoded transmission.
  3 BIG COLOR   one colored measure -> MSRP, Blues sequential gradient (>=5 rows).
  4 BAND        Big Color present -> LIGHT washed-blue band (#EAF0F6).
  5 SMALL COLOR hairlines, striping (10 rows), stub tint, group emphasis, fmt_currency.
  6 TITLES      title + subtitle (states the MSRP definition) + source note.
  7 RENDER      .gtsave("table.png") + .as_raw_html() -> table.html
"""
import numpy as np
import pandas as pd
from great_tables import GT, style, loc

# ---- Step 1: understand + clean --------------------------------------------
df = pd.read_csv("gtcars.csv")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")   # ensure real float for fmt/data_color

# One human label per row instead of separate mfr/model columns.
df["car"] = df["mfr"].str.strip() + " " + df["model"].str.strip()

# Decode the terse drivetrain / transmission codes into readable labels.
df["drive"] = df["drivetrain"].str.strip().str.upper()    # rwd -> RWD, awd -> AWD

_TR = {"a": "automatic", "m": "manual", "am": "automated manual", "dd": "dual-clutch"}
def decode_trsmn(code: str) -> str:
    code = str(code).strip()
    gears, suffix = code[:1], code[1:]
    return f"{gears}-speed {_TR.get(suffix, suffix)}"
df["transmission"] = df["trsmn"].map(decode_trsmn)

# ---- Step 2: organize columns ----------------------------------------------
# "10 most expensive" = highest MSRP (single, reproducible definition).
top = df.sort_values("msrp", ascending=False).head(10).copy()

# Order countries by their most expensive car, then cars within a country by MSRP,
# so each group is contiguous and groups run priciest-first.
country_rank = top.groupby("ctry_origin")["msrp"].max().rank(ascending=False)
top["_crank"] = top["ctry_origin"].map(country_rank)
top = top.sort_values(["_crank", "msrp"], ascending=[True, False]).reset_index(drop=True)
top = top[["car", "ctry_origin", "msrp", "drive", "transmission"]]

# ---- Step 3: Big Color -- MSRP gradient (neutral magnitude -> Blues) --------
lo = float(np.nanmin(top[["msrp"]].to_numpy()))
hi = float(np.nanmax(top[["msrp"]].to_numpy()))

# ---- Build the table --------------------------------------------------------
gt = (
    GT(top, rowname_col="car", groupname_col="ctry_origin")
    # Step 6: titles + subtitle (states the definition) + source note
    .tab_header(
        title="The World's Priciest Grand Tourers",
        subtitle="The 10 most expensive GT cars by manufacturer's suggested retail price, grouped by country of origin",
    )
    .tab_stubhead(label="Car")
    .cols_label(msrp="MSRP", drive="Drivetrain", transmission="Transmission")
    # Step 5e: format the measure
    .fmt_currency(columns="msrp", currency="USD", decimals=0, use_seps=True)
    # Step 3: gradient fill on the single hero measure
    .data_color(
        columns="msrp",
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    .cols_align(align="left", columns=["drive", "transmission"])
    .cols_align(align="right", columns="msrp")
    # Step 5c: striping (10 rows, body not fully color-filled)
    .opt_row_striping()
    # Step 5d: stub tint -- washed-blue to harmonize with the Blues Big Color
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    # Step 5a: hairlines + column-label bottom rule; Step 4: light washed-blue band;
    # Step 5 sub-note: row-group emphasis (light fill + bold); Frame border on all 4 sides.
    .tab_options(
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        row_striping_background_color="#F6F6F6",
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        row_group_background_color="#EAF0F6",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    .tab_source_note(source_note="Source: gtcars dataset (Posit / great_tables sample data).")
)

# ---- Step 7: render + embed -------------------------------------------------
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())
print("Wrote table.png and table.html")
