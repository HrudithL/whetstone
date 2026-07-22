---
name: pptx
description: Use when the user asks for a PowerPoint deck, slides, a pitch deck, or a .pptx — building presentation slides from an outline or brief. Generates a Python script using python-pptx that lays out titled slides with consistent, readable design and saves a .pptx. Invoke before writing any Python: the deck plan (layout, type, palette) shapes the whole script.
---

# PPTX (slide decks)

Build presentation decks in Python with **python-pptx**. Produce one deck that reads as a single,
consistent product: a coherent type scale, a small palette, and a predictable slide layout.

## Workflow

1. **Plan the deck** from the brief: the slide sequence (title slide → one idea per content slide),
   a small palette (a background, a text color, one accent), and a type treatment (one family, a
   title size and a body size).
2. **Build it** with `python-pptx`:
   - `from pptx import Presentation`, `from pptx.util import Inches, Pt`, and (as needed)
     `from pptx.dml.color import RGBColor`, `from pptx.enum.text import PP_ALIGN`.
   - Add slides from layouts (`prs.slide_layouts[...]`); set each slide's title and body text.
   - Style deliberately: set `run.font.name`, `run.font.size = Pt(...)`, `run.font.color.rgb =
     RGBColor(...)`, and paragraph `alignment` where it serves the design.
   - Keep one slide per idea; do not overfill.
3. **Save and verify**: `prs.save("deck.pptx")`, then run the script so the `.pptx` is actually
   produced.

## Defaults (used only absent an instruction)

- A clean, legible sans-serif family, titles noticeably larger than body.
- Titles read top-aligned and, by convention, **centered** unless the design says otherwise.
- A light slide background with dark text and a single restrained accent color.
- Generous margins; a handful of bullets per slide at most.

## Rule 0 — the user's instructions override every default

Every default above is just a default. Any explicit instruction in the prompt or the learned layer
(a specific font, title alignment, slide size, background color, accent) **wins** — apply it exactly
to every slide and drop the conflicting default silently. The defaults decide what to do only *in
the absence of* an instruction; they never override one.
