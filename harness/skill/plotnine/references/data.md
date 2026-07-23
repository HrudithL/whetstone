# data.md — get to one clean, correctly-typed, TIDY DataFrame

plotnine maps **columns** to aesthetics (`x`, `y`, `color`, `fill`, `facet`). Everything
downstream assumes the frame is clean and **tidy** (long form). Do this in pandas *before*
you build the plot — fixing it with layered geoms afterward is far more brittle.

## Correct types first

- **Currency / percent / number strings** → strip to floats before plotting. plotnine (via
  matplotlib) does not parse `"$1,200"` or `"12%"`; convert:
  ```python
  df["msrp"] = df["msrp"].replace(r"[\$,]", "", regex=True).astype(float)
  df["rate"] = df["rate"].str.rstrip("%").astype(float) / 100
  ```
- **`object`-dtype numerics** → `pd.to_numeric(df[c], errors="coerce")`.
- **Dates** → `pd.to_datetime(df[c])`. A date axis needs real datetimes, not strings, or
  ticks sort lexically and `scale_x_date` won't work.
- **Ordered categoricals** (months, sizes S/M/L, Low/Med/High) → set an explicit order so
  the axis/legend isn't alphabetical:
  ```python
  df["size"] = pd.Categorical(df["size"], categories=["S", "M", "L", "XL"], ordered=True)
  ```

## Tidy / long form (the important one)

A tidy frame has **one row per observation** and **one column per variable**. If you have
several series in separate columns (a classic wide frame), **melt** so the series becomes
one grouping column you can map to `color`/`fill`:

```python
# wide: year, revenue_north, revenue_south, revenue_east  → long
long = df.melt(
    id_vars="year",
    value_vars=["revenue_north", "revenue_south", "revenue_east"],
    var_name="region", value_name="revenue",
)
long["region"] = long["region"].str.replace("revenue_", "", regex=False)
# now: aes("year", "revenue", color="region")
```

Rule of thumb: **if you're about to add a second `geom_line`/`geom_col` layer just to draw
another column, melt instead** and map the group to a color aesthetic.

## Aggregate before plotting when the geom expects summarized data

- `geom_col` draws `y` as-is (`stat="identity"`), so aggregate first
  (`df.groupby(...)[m].sum()/.mean().reset_index()`).
- `geom_bar` counts rows for you (`stat="count"`) — use it for raw category frequencies,
  not pre-aggregated totals.

## Missing values

Decide what missing means before plotting. `dropna(subset=[...])` on the mapped columns is
usually right for a scatter/line (a NaN can't be positioned), but say so — don't silently
drop rows that change what the plot claims. For a bar of counts, a missing category may be
a real "unknown" bucket worth keeping.

## Validate the request against the data

If the prompt asks for a variable that isn't in the frame, or a comparison the grain can't
support (e.g. a per-day trend from monthly data), **stop and say so** — do not fabricate a
column or silently plot something else.
