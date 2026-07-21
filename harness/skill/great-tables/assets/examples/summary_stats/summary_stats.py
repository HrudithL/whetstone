"""Summary-statistics archetype — distilled reference example.

Data: data/pizzaplace.csv  (49,574 individual pizza orders)
Story: Per-category, per-size sales totals with subtotals per category
       and a grand total at the bottom.
"""
import pandas as pd
from great_tables import GT, loc, style

df = pd.read_csv("data/pizzaplace.csv")

agg = (
    df.groupby(["type", "size"])
      .agg(orders=("id", "count"),
           revenue=("price", "sum"),
           avg_price=("price", "mean"))
      .reset_index()
)

# Ordered Categorical on size so rows land S → M → L → XL → XXL rather than
# alphabetic. Without ordered=True pandas would default to L, M, S, XL, XXL.
size_order = ["S", "M", "L", "XL", "XXL"]
agg["size"] = pd.Categorical(agg["size"], categories=size_order, ordered=True)
agg["type"] = agg["type"].map({"classic": "Classic", "veggie": "Veggie",
                                "chicken": "Chicken", "supreme": "Supreme"})
agg = agg.sort_values(["type", "size"]).reset_index(drop=True)

(
    # rowname_col + groupname_col is the gt-native way to express a two-level
    # row layout: group banners on `type`, indented size labels under each.
    GT(agg, rowname_col="size", groupname_col="type")
    .tab_header(
        title="Pizza Sales by Category and Size",
        subtitle="Full-year totals across the four menu categories",
    )
    .cols_label(orders="Orders", revenue="Revenue", avg_price="Avg. price")
    .fmt_currency(columns=["revenue", "avg_price"], currency="USD", decimals=2)
    .fmt_integer(columns=["orders"])
    # Grand summary row at the bottom — the headline number a manager carries
    # away. Callable form returning pd.Series is the pandas escape; pl.col
    # expressions only work on polars-backed tables. avg_price is omitted
    # because a mean-of-means is not meaningful.
    .grand_summary_rows(
        fns={"All categories": lambda d: pd.Series({
            "orders": int(d["orders"].sum()),
            "revenue": float(d["revenue"].sum()),
        })},
        missing_text="",
    )
    # Bold the group banners so the four categories visually punctuate the rows.
    .tab_style(style=style.text(weight="bold"), locations=loc.row_groups())
    .cols_align(align="right", columns=["orders", "revenue", "avg_price"])
    .tab_source_note(source_note="Source: pizzaplace dataset (Posit / great_tables sample data).")
)
