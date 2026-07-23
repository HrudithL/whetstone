# big_color.md — the ONE color-encoded variable, palette by data shape

**Big Color** is the plot's primary data encoding: the single hero variable you map to
`color=`/`fill=`. **Ceiling: ≤ 1 color-encoded variable.** If nothing in the data earns
color, use the single house accent (bottom section) and drop the legend.

Pick the section by your hero variable's *shape*, then **copy the exact hexes / scale
object below**. Do not invent a palette. These match `scripts/pn_house_style.py`
(`house_palette(kind=...)`), which is the preferred way to apply them.

---

## Qualitative — categorical, unordered groups

Colorblind-safe **Okabe–Ito** palette (use in this order; it degrades gracefully as you
use fewer):

```
#0072B2  blue
#E69F00  orange
#009E73  bluish green
#CC79A7  reddish purple
#56B4E9  sky blue
#D55E00  vermillion
#F0E442  yellow          (use last — low contrast on white)
#000000  black           (use last)
```

Apply:
```python
from plotnine import scale_color_manual, scale_fill_manual
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
... + scale_color_manual(values=OKABE_ITO, name="Region")   # or scale_fill_manual for bars/areas
```
Or: `house_palette("qualitative", aes="color")`.

If categories exceed ~6, prefer **facets** over more colors (see `geoms.md`).

## Sequential — ordered magnitude, one direction (low → high)

**viridis** (perceptually uniform, colorblind-safe):

```python
from plotnine import scale_color_cmap, scale_fill_cmap
... + scale_fill_cmap(cmap_name="viridis", name="Population")   # continuous fill (tiles, gradient bars)
... + scale_color_cmap(cmap_name="viridis", name="Population")  # continuous color (points/lines)
```
Or: `house_palette("sequential", aes="fill")`.

For a discrete ordered factor (Low/Med/High) use `scale_*_cmap_d(cmap_name="viridis")`.

## Diverging — signed values around a reference (neg/pos, below/above target)

Red–blue diverging, **centered on the reference point** (0 for a plain delta):

```python
from plotnine import scale_fill_gradient2, scale_color_gradient2
... + scale_fill_gradient2(low="#B2182B", mid="#F7F7F7", high="#2166AC",
                           midpoint=0, name="Change")
```
- Set `midpoint=` to the true reference (0 for a delta, 1.0 for a ratio stored as a
  fraction, 100 for a percentage-point ratio).
- Keep the color scale **symmetric** about the midpoint so equal magnitudes read equally —
  set matching `limits=(-b, b)` where `b = max(abs(min), abs(max))`.

Or: `house_palette("diverging", aes="fill", midpoint=0)`.

## No hero variable → single house accent, no legend

A plot whose story is the geom itself (a single-series line, one distribution, an
un-grouped bar/scatter) gets **one** neutral accent and **no** color legend:

```
HOUSE_ACCENT = "#2C6FB3"    # muted professional blue
```
```python
... geom_col(fill="#2C6FB3")          # constant color OUTSIDE aes()  → no legend
... geom_point(color="#2C6FB3", alpha=0.5)
```
Setting a color as a **constant argument** (outside `aes()`) is what suppresses the legend;
mapping it *inside* `aes()` would create a spurious one-item legend — don't.
