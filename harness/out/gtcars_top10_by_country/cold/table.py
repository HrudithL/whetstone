"""Top 10 most expensive gtcars, grouped by country of origin.

Story: the 10 priciest grand tourers, organized by where they're built, with
each car's drivetrain and transmission. MSRP is the single hero measure and is
color-encoded as a Blues column gradient.
"""
import re

import numpy as np
import pandas as pd
from great_tables import GT, md, style, loc

# ── Step 1: understand + clean the data ───────────────────────────────────────
# gtcars.csv is already correctly typed (msrp/hp are float64). No string parsing
# needed — just derive the display fields.
df = pd.read_csv("gtcars.csv")

# One human label per car; two split mfr/model columns force a mental join.
df["car"] = df["mfr"] + " " + df["model"]


def decode_trsmn(code: str) -> str:
    """'7a' -> '7-spd Automatic', '8am' -> '8-spd Automated Manual'."""
    m = re.match(r"(\d+)([a-z]+)", str(code))
    if not m:
        return str(code)
    n, kind = m.group(1), m.group(2)
    names = {
        "a": "Automatic",
        "m": "Manual",
        "am": "Automated Manual",
        "dct": "Dual-Clutch",
    }
    return f"{n}-spd {names.get(kind, kind.upper())}"


df["drivetrain"] = df["drivetrain"].str.upper()          # rwd -> RWD, awd -> AWD
df["trsmn"] = df["trsmn"].apply(decode_trsmn)

# ── Step 2: organize columns ──────────────────────────────────────────────────
# Top 10 by price. The sort IS the message.
top = df.nlargest(10, "msrp").copy()

# Group order = countries ranked by their most expensive car; within each
# country, cars descend by price. groupname_col keeps rows contiguous by group.
top["_grp_rank"] = top.groupby("ctry_origin")["msrp"].transform("max")
top = top.sort_values(["_grp_rank", "msrp"], ascending=[False, False])

top = top[["ctry_origin", "car", "drivetrain", "trsmn", "msrp"]]

# ── Step 3: Big Color — MSRP is the lone hero measure (neutral magnitude, ─────
#            ordered, 10 rows) -> Blues column gradient. Data-driven domain.
lo = float(np.nanmin(top["msrp"].to_numpy()))
hi = float(np.nanmax(top["msrp"].to_numpy()))

gt = (
    GT(top, rowname_col="car", groupname_col="ctry_origin")
    # ── Step 6: titles & annotations ──────────────────────────────────────────
    .tab_header(
        title="The World's Priciest Grand Tourers",
        subtitle=md(
            "Top 10 gtcars by MSRP, grouped by country of origin — "
            "with drivetrain and transmission"
        ),
    )
    .tab_spanner(label="Powertrain", columns=["drivetrain", "trsmn"])
    .cols_label(
        drivetrain="Drivetrain",
        trsmn="Transmission",
        msrp="MSRP",
    )
    .tab_stubhead(label="Car")
    # ── Step 5(e): format per semantic type ───────────────────────────────────
    .fmt_currency(columns="msrp", currency="USD", decimals=0)
    # ── Step 3: the gradient fill ─────────────────────────────────────────────
    .data_color(
        columns="msrp",
        palette="Blues",
        domain=[lo, hi],
        truncate=False,
        na_color="#808080",
    )
    .cols_align(align="left", columns=["drivetrain", "trsmn"])
    .cols_align(align="right", columns="msrp")
    # ── Step 5(c): row striping (10 rows, body not fully color-filled) ────────
    .opt_row_striping()
    # ── Step 5(a): cell hairlines + column-label bottom rule ──────────────────
    .tab_options(
        table_body_hlines_style="solid",
        table_body_hlines_color="#E8E8E8",
        table_body_hlines_width="1px",
        column_labels_border_bottom_color="#CCCCCC",
        column_labels_border_bottom_width="2px",
        # ── Step 4: Big Color present -> LIGHT band (washed Blues tint) ────────
        column_labels_background_color="#EAF0F6",
        column_labels_font_weight="bold",
        row_striping_background_color="#F6F6F6",
        # ── Step 5 sub-note: row-group emphasis (fill + bold, consistent hue) ──
        row_group_background_color="#EAF0F6",
        row_group_font_weight="bold",
        row_group_border_top_color="#BDBDBD",
        row_group_border_bottom_color="#BDBDBD",
        row_group_padding="6px",
        # ── Global Frame constant: boxed border on all four sides ─────────────
        table_border_top_style="solid", table_border_top_color="#CCCCCC", table_border_top_width="1px",
        table_border_bottom_style="solid", table_border_bottom_color="#CCCCCC", table_border_bottom_width="1px",
        table_border_left_style="solid", table_border_left_color="#CCCCCC", table_border_left_width="1px",
        table_border_right_style="solid", table_border_right_color="#CCCCCC", table_border_right_width="1px",
    )
    # ── Step 5(d): stub tint, harmonized to the washed Blues tint ─────────────
    .tab_style(style=style.fill(color="#EAF0F6"), locations=loc.stub())
    # ── Step 5(b): vertical divider at the Powertrain group boundary ──────────
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.body(columns="trsmn"),
    )
    .tab_style(
        style=style.borders(sides="right", color="#D0D0D0", weight="1px"),
        locations=loc.column_labels(columns="trsmn"),
    )
    .tab_source_note(
        source_note=md("Source: **gtcars** dataset (Posit / great_tables sample data).")
    )
)

# ── Step 7: render + write embeddable HTML ────────────────────────────────────
gt.gtsave("table.png", expand=15)
with open("table.html", "w") as f:
    f.write(gt.as_raw_html())

print("Wrote table.png and table.html")
