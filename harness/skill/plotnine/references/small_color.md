# small_color.md — the quiet polish: theme, gridlines, text, save()

**Small Color** is everything that isn't the data encoding: the theme, backgrounds,
gridlines, text, and legend placement. All neutral, all pinned here. Run this checklist
top to bottom at Step 5, then save with the pinned size/dpi. The preferred way to apply
all of it is `apply_house_style(p)` + `save_plot(p, "plot.png")` from
`scripts/pn_house_style.py`; the values below are what that helper encodes.

## The fixed checklist

1. **Base theme.** Start from `theme_minimal(base_size=12)` — light, low-chrome, lets the
   data lead. Never mix themes across a session.
2. **Panel & background.** White plot background; **no** heavy panel border or grey panel
   fill (theme_minimal already gives this). Do not add `theme_gray`'s grey panel back.
3. **Gridlines.** Keep **major** gridlines only, thin and light grey `#E6E6E6`; **remove
   minor** gridlines. They orient the eye without competing with the data:
   ```python
   from plotnine import theme, element_line, element_blank
   theme(panel_grid_major=element_line(color="#E6E6E6", size=0.4),
         panel_grid_minor=element_blank())
   ```
4. **Text sizes & hierarchy** (relative scale title > axis titles > tick labels):
   - title 15, bold · axis titles 12 · tick labels 10 · legend title 11 · legend text 10.
   - Title left-aligned reads as a caption; centered is also fine — pick left and keep it.
   ```python
   from plotnine import element_text
   theme(plot_title=element_text(size=15, weight="bold"),
         axis_title=element_text(size=12),
         axis_text=element_text(size=10),
         legend_title=element_text(size=11),
         legend_text=element_text(size=10))
   ```
5. **Text color.** All text `#222222` (near-black, softer than pure black). Tick/axis
   lines the same light grey as gridlines.
6. **Legend.** Position `"right"` by default; `"bottom"` when the plot is wide/short or the
   legend is a single row. A constant-color (un-mapped) plot has **no** legend — see
   `big_color.md`.
7. **Axis number/date formatting.** Big numbers get thousands separators, money a `$`,
   shares a `%`; dates get readable ticks. Use the `scale_*` calls in `api.md` — never ship
   `1e6` or `2024-01-01T00:00:00` tick labels.

## Frame / save

- **Figure size:** `(8, 5)` inches (landscape) for most plots; `(6, 7)` for a tall
  horizontal-bar ranking. This is `figure_size` in `theme(...)` and/or `width`/`height` in
  `save()`.
- **dpi:** `200` — crisp without being huge.
- **Save call (the only renderer):**
  ```python
  p.save("plot.png", width=8, height=5, dpi=200, verbose=False)
  ```
  `verbose=False` silences plotnine's size/dpi info lines. Never call `plt.show()`.

## The neutral hexes (single source of truth)

```
gridline / axis    #E6E6E6
text               #222222
background         #FFFFFF (white)
house accent       #2C6FB3   (see big_color.md — used when no variable is color-encoded)
```
