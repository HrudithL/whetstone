"""Build the 5-slide "Marrow" pitch deck.

Marrow is a CLI that maps a repo's tests to the code they actually cover.
One idea per slide; run this script to write deck.pptx alongside it.

Design: light background, dark ink, one restrained accent. A single sans-serif
family (Arial) with a fixed type scale, and titles top-aligned and centered.
"""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# --- Palette -------------------------------------------------------------
BG = RGBColor(0xFA, 0xFA, 0xF8)      # warm near-white page
INK = RGBColor(0x17, 0x18, 0x1A)     # near-black body/title text
MUTED = RGBColor(0x5F, 0x63, 0x67)   # secondary text
ACCENT = RGBColor(0xB0, 0x40, 0x2F)  # marrow red, the single accent
CHIP = RGBColor(0xF0, 0xEC, 0xE6)    # tint behind code

# --- Type ----------------------------------------------------------------
FONT = "Arial"
MONO = "Consolas"
SZ_HERO = Pt(76)      # deck title
SZ_TITLE = Pt(38)     # slide titles
SZ_LEAD = Pt(23)      # lead / subtitle
SZ_BODY = Pt(18)      # body copy
SZ_STEP = Pt(15)      # step copy in the three-column slide
SZ_MICRO = Pt(11)     # slide numbers

# --- Geometry ------------------------------------------------------------
DECK_W, DECK_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(1.0)
CONTENT_W = DECK_W - 2 * MARGIN
TITLE_TOP = Inches(0.85)

prs = Presentation()
prs.slide_width, prs.slide_height = DECK_W, DECK_H
BLANK = prs.slide_layouts[6]


def add_slide():
    """A blank slide painted with the deck background."""
    slide = prs.slides.add_slide(BLANK)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, DECK_W, DECK_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    return slide


def textbox(slide, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    return tf


def write(tf, spans, size, color, align=PP_ALIGN.CENTER, font=FONT,
          bold=False, space_after=Pt(0), line=0.0, first=False):
    """Append a paragraph built from one string or a list of run specs."""
    para = tf.paragraphs[0] if first else tf.add_paragraph()
    para.alignment = align
    para.space_after = space_after
    if line:
        para.line_spacing = line
    for span in [spans] if isinstance(spans, str) else spans:
        text, over = (span, {}) if isinstance(span, str) else span
        run = para.add_run()
        run.text = text
        run.font.name = over.get("font", font)
        run.font.size = over.get("size", size)
        run.font.bold = over.get("bold", bold)
        run.font.color.rgb = over.get("color", color)
    return para


def rule(slide, top, width=Inches(1.6), color=ACCENT, height=Pt(4)):
    """Short accent rule, horizontally centered."""
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, (DECK_W - width) // 2, top, width, height
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def title_block(slide, title, number):
    """Centered, top-aligned slide title over an accent rule + slide number."""
    tf = textbox(slide, MARGIN, TITLE_TOP, CONTENT_W, Inches(1.1))
    write(tf, title, SZ_TITLE, INK, bold=True, line=1.05, first=True)
    rule(slide, TITLE_TOP + Inches(1.02))
    num = textbox(slide, DECK_W - MARGIN - Inches(1.0),
                  DECK_H - Inches(0.72), Inches(1.0), Inches(0.3))
    write(num, f"{number}/5", SZ_MICRO, MUTED, align=PP_ALIGN.RIGHT, first=True)


def statement_slide(title, lead, body, number):
    """Slide title + one bold lead line + supporting sentence."""
    slide = add_slide()
    title_block(slide, title, number)
    tf = textbox(slide, Inches(1.85), Inches(2.9), DECK_W - 2 * Inches(1.85),
                 Inches(2.4), anchor=MSO_ANCHOR.TOP)
    write(tf, lead, SZ_LEAD, ACCENT, bold=True, line=1.25,
          space_after=Pt(18), first=True)
    write(tf, body, SZ_BODY, MUTED, line=1.45)
    return slide


def code_chip(slide, text, left, top, width, size=Pt(15)):
    """Mono text on a tinted rounded plate."""
    height = Inches(0.62)
    chip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top,
                                  width, height)
    chip.fill.solid()
    chip.fill.fore_color.rgb = CHIP
    chip.line.fill.background()
    chip.shadow.inherit = False
    chip.adjustments[0] = 0.18
    tf = chip.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.18)
    tf.margin_top = tf.margin_bottom = 0
    write(tf, text, size, INK, font=MONO, first=True)
    return chip


# --- 1. Title ------------------------------------------------------------
slide = add_slide()
tf = textbox(slide, MARGIN, Inches(2.35), CONTENT_W, Inches(1.6))
write(tf, "Marrow", SZ_HERO, INK, bold=True, first=True)
rule(slide, Inches(3.98), width=Inches(2.0))
tf = textbox(slide, MARGIN, Inches(4.42), CONTENT_W, Inches(1.2))
write(tf, "Know what your tests actually cover.", SZ_LEAD, MUTED,
      space_after=Pt(14), first=True)
write(tf, "A CLI that maps a repo's tests to the code they cover.",
      Pt(15), MUTED)

# --- 2. The problem ------------------------------------------------------
statement_slide(
    "Big test suites hide their gaps.",
    "Nobody knows which tests cover which code.",
    "Large suites are slow, and the mapping from test to code lives only in "
    "people's heads. So dead tests linger for years, and real gaps in "
    "coverage go unnoticed.",
    2,
)

# --- 3. The idea ---------------------------------------------------------
statement_slide(
    "Watch one run. Draw the real map.",
    "One instrumented test run is enough.",
    "Marrow instruments a single test run and produces a test→code "
    "coverage map — no annotations, no config.",
    3,
)

# --- 4. How it works -----------------------------------------------------
slide = add_slide()
title_block(slide, "How it works", 4)
steps = [
    ("Run your suite", "Prefix the test command you already use:",
     "marrow watch -- <your test cmd>"),
    ("Marrow watches", "It records which lines each test exercised, as the "
     "suite runs.", None),
    ("Read the map", "You get an interactive test→code map, plus a list "
     "of dead tests and untested lines.", None),
]
gap = Inches(0.5)
col_w = (CONTENT_W - 2 * gap) // 3
for i, (heading, body, code) in enumerate(steps):
    left = MARGIN + i * (col_w + gap)
    bar = rule(slide, Inches(2.62), width=col_w, color=CHIP, height=Pt(3))
    bar.left = left  # rule() centers; nudge it over this column
    ntf = textbox(slide, left, Inches(2.82), col_w, Inches(0.5))
    write(ntf, f"0{i + 1}", Pt(14), ACCENT, align=PP_ALIGN.LEFT, bold=True,
          first=True)
    ttf = textbox(slide, left, Inches(3.32), col_w, Inches(2.0))
    write(ttf, heading, Pt(20), INK, align=PP_ALIGN.LEFT, bold=True,
          space_after=Pt(10), first=True)
    write(ttf, body, SZ_STEP, MUTED, align=PP_ALIGN.LEFT, line=1.4)
    if code:
        code_chip(slide, code, left, Inches(4.86), col_w, size=Pt(11))

# --- 5. Call to action ---------------------------------------------------
slide = add_slide()
title_block(slide, "Install Marrow", 5)
code_chip(slide, "pipx install marrow", (DECK_W - Inches(4.2)) // 2,
          Inches(3.15), Inches(4.2), size=Pt(20))
tf = textbox(slide, MARGIN, Inches(4.24), CONTENT_W, Inches(1.4))
write(tf, "Works with pytest, Jest, go test.", SZ_LEAD, INK, bold=True,
      space_after=Pt(14), first=True)
write(tf, "Point it at the suite you already have, and see the real map.",
      Pt(15), MUTED)

prs.save("deck.pptx")
print(f"Wrote deck.pptx — {len(prs.slides)} slides")
