"""The 10 most expensive GT cars, grouped by country of origin.

Flowchart trace:
  Step 1 data     : clean CSV -> one typed DataFrame; compose `car`, take top 10 by MSRP.
  Step 2 columns  : stub=car, groupname_col=ctry_origin (prompt says "grouped by country"),
                    "Powertrain" spanner over drivetrain + transmission, hero = MSRP.
  Step 3 BigColor : MSRP is an ordered neutral magnitude over >=5 rows -> Blues gradient (hero).
  Step 4 band     : Big Color present -> LIGHT washed-blue band (#EAF0F6).
  Step 5 small    : hairlines, group divider, striping, washed-blue stub tint, fmt_currency;
                    row groups recoloured teal (#0F766E) + white text per learned preference.
  Step 6 titles   : title + subtitle + source note.
  Step 7 render   : .gtsave("table.png") + .as_raw_html() -> table.html.
"""
import numpy as np
import pandas as pd
from great_tables import GT, style, loc

# --- Step 1: one clean, correctly-typed DataFrame -------------------------------
df = pd.read_csv("gtcars.csv")
df["msrp"] = pd.to_numeric(df["msrp"], errors="coerce")   # ensure real numeric for fmt/color
df["ctry_origin"] = df["ctry_origin"].str.strip()         # clean group keys

# One human-readable label per row (avoid forcing mfr+model to combine mentally).
df["car"] = df["mfr"].str.strip() + " " + df["model"].str.strip()

# Tidy the powertrain codes for display.
df["drivetrain"] = df["drivetrain"].str.upper()
df["trsmn"] = df["trsmn"].str.upper()

# The sort IS the message: 10 most expensive.
top = df.sort_values("msrp", ascending=False).head(10).reset_index(drop=True)
top = top[["car", "ctry_origin", "drivetrain", "trsmn", "msrp"]]

# --- Step 3 domain: data-driven, backend-neutral --------------------------------
lo = float(np.nanmin(top[["msrp"]].to_numpy()))
hi = float(np.nanmax(top[["msrp"]].to_numpy()))

gt = (
    GT(top, rowname_col="car", groupname_col="ctry_origin")
    # --- Step 6: titles & source ------------------------------------------------
    .tab_header(
        title="The 10 Most Expensive GT Cars",
        subtitle="Ranked by manufacturer's suggested retail price, grouped by country of origin",
    )
    .tab_stubhead(label="Car")
    # --- Step 2: labels + Powertrain spanner ------------------------------------
    .cols_label(drivetrain="Drivetrain", trsmn="Transmission", msrp="MSRP")
    .tab_spanner(label="Powertrain", columns=["drivetrain", "trsmn"])
    # --- Step 5(e): formatting per column ---------------------------------------
    .fmt_currency(columns=["msrp"], currency="USD", decimals=0)
    .sub_missing(columns=["msrp"], missing_text="—")
    .cols_align(align="center", columns=["drivetrain", "trsmn"])
    .cols_align(align="right", columns=["msrp"])
    # --- Step 3: Big Color — MSRP magnitude gradient (Blues) ---------------------
    .data_color(
        columns=["msrp"],
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    # --- Step 4: LIGHT washed-blue heading band (Big Color present) --------------
    .tab_options(
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # Step 5(a): hairline between every body row
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        # Step 5: row-group structural rule + air
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_font_weight="bold",
        row_group_padding="6px",
        # Step 5(c): row striping (10 rows; body not full-filled by Big Color)
        row_striping_background_color="#F6F6F6",
        # Frame — boxed light border on all four sides
        table_border_top_style="solid",    table_border_top_color="#CCCCCC",    table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid",   table_border_left_color="#CCCCCC",   table_border_left_width="1px",
        table_border_right_style="solid",  table_border_right_color="#CCCCCC",  table_border_right_width="1px",
    )
    .opt_row_striping()
    # --- Step 5(d): washed-blue stub tint (harmonized to Blues Big Color) --------
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    # --- Step 5(b): vertical divider at the Powertrain group boundary ------------
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="trsmn"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="trsmn"),
    )
    # --- Learned preference (L2): teal country row-group labels, white text ------
    .tab_style(
        style=[style.fill(color="#0F766E"), style.text(color="white")],
        locations=loc.row_groups(),
    )
    .tab_source_note(source_note="Source: gtcars dataset (Posit / great_tables sample data).")
)

gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())
print("Wrote table.png and table.html")
