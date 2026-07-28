"""Build the 5-slide "Marrow" pitch deck described in pitch_deck_outline.md.

Slides follow the outline order exactly:
  1. Title            2. The problem      3. The idea
  4. How it works     5. Call to action

Run:  python3 deck.py   ->   deck.pptx
"""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# ---------------------------------------------------------------- design system

BG = RGBColor(0xFA, 0xF8, 0xF5)      # warm off-white slide background
INK = RGBColor(0x1C, 0x1B, 0x19)     # primary text
MUTED = RGBColor(0x6B, 0x66, 0x5F)   # secondary text
ACCENT = RGBColor(0xC2, 0x47, 0x2F)  # single restrained accent (rust)
CARD = RGBColor(0xFF, 0xFF, 0xFF)    # card fill
HAIRLINE = RGBColor(0xE2, 0xDD, 0xD5)

FONT = "Arial"        # one clean sans-serif family, used everywhere
MONO = "Consolas"     # commands only

DECK_TITLE = Pt(62)
SLIDE_TITLE = Pt(34)
LEAD = Pt(22)
BODY = Pt(18)
STEP = Pt(16)
FOOTER = Pt(10)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.9)
CONTENT_W = SLIDE_W - 2 * MARGIN

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]

# ---------------------------------------------------------------- helpers


def new_slide():
    """Blank slide with the deck background painted in."""
    slide = prs.slides.add_slide(BLANK)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    return slide


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    return tf


def write(tf, text, size, color=INK, bold=False, align=PP_ALIGN.CENTER,
          font=FONT, space_before=0, space_after=0, line=None, first=False):
    """Append (or fill) a styled paragraph. Returns the paragraph."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    if line is not None:
        p.line_spacing = line
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = size
    run.font.bold = bold
    run.font.color.rgb = color
    return p


def accent_rule(slide, y, width=Inches(1.5), centered=True, x=None,
                thickness=Inches(0.045), color=ACCENT):
    """Short accent bar — the deck's recurring visual motif."""
    left = int((SLIDE_W - width) / 2) if centered else x
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, y, width, thickness)
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def slide_title(slide, text, size=SLIDE_TITLE):
    """Top-aligned, centered title with an accent rule beneath it."""
    tf = textbox(slide, MARGIN, Inches(0.85), CONTENT_W, Inches(1.35))
    write(tf, text, size, INK, bold=True, line=1.1, first=True)
    accent_rule(slide, Inches(2.28))


def footer(slide, number):
    tf = textbox(slide, MARGIN, Inches(6.72), Inches(3.0), Inches(0.3))
    write(tf, "Marrow", FOOTER, MUTED, align=PP_ALIGN.LEFT, first=True)
    tf = textbox(slide, SLIDE_W - MARGIN - Inches(3.0), Inches(6.72),
                 Inches(3.0), Inches(0.3))
    write(tf, str(number), FOOTER, MUTED, align=PP_ALIGN.RIGHT, first=True)


def bullets(slide, lines, top, width=Inches(9.4)):
    """Left-aligned bullet column, centered on the slide."""
    x = int((SLIDE_W - width) / 2)
    tf = textbox(slide, x, top, width, Inches(2.6))
    for i, text in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(16)
        p.line_spacing = 1.3
        dot = p.add_run()
        dot.text = "•   "
        dot.font.name = FONT
        dot.font.size = BODY
        dot.font.bold = True
        dot.font.color.rgb = ACCENT
        run = p.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = BODY
        run.font.color.rgb = INK


# ---------------------------------------------------------------- 1. Title

s = new_slide()
tf = textbox(s, MARGIN, Inches(2.55), CONTENT_W, Inches(1.3))
write(tf, "Marrow", DECK_TITLE, INK, bold=True, first=True)
accent_rule(s, Inches(3.95), width=Inches(2.0))
tf = textbox(s, MARGIN, Inches(4.35), CONTENT_W, Inches(0.7))
write(tf, "Know what your tests actually cover.", LEAD, MUTED, first=True)
tf = textbox(s, MARGIN, Inches(6.62), CONTENT_W, Inches(0.4))
write(tf, "A CLI that maps a repo's tests to the code they actually cover.",
      FOOTER, MUTED, first=True)

# ---------------------------------------------------------------- 2. The problem

s = new_slide()
slide_title(s, "Big test suites hide their gaps.")
bullets(s, [
    "Large suites are slow — a full run is a coffee break, not a feedback loop.",
    "Nobody knows which tests cover which code.",
    "So dead tests linger, and real gaps go unnoticed.",
], Inches(3.05))
footer(s, 2)

# ---------------------------------------------------------------- 3. The idea

s = new_slide()
slide_title(s, "Watch one run. Draw the real map.")
tf = textbox(s, Inches(2.1), Inches(3.1), SLIDE_W - 2 * Inches(2.1), Inches(1.6))
write(tf, "Marrow instruments a single test run and produces a "
          "test→code coverage map.", LEAD, INK, line=1.35, first=True)
tf = textbox(s, MARGIN, Inches(4.62), CONTENT_W, Inches(0.6))
write(tf, "No annotations.   No config.", BODY, ACCENT, bold=True, first=True)
footer(s, 3)

# ---------------------------------------------------------------- 4. How it works

s = new_slide()
slide_title(s, "How it works")

steps = [
    ("01", "Run", "marrow watch -- <your test cmd>", ""),
    ("02", "", "", "Marrow records which lines each test exercised."),
    ("03", "", "", "It emits an interactive map, plus a list of dead tests "
                   "and untested lines."),
]

gap = Inches(0.5)
col_w = int((CONTENT_W - 2 * gap) / 3)
card_top, card_h = Inches(2.95), Inches(2.75)

for i, (num, prefix, code, plain) in enumerate(steps):
    x = MARGIN + i * (col_w + gap)

    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, card_top,
                              col_w, card_h)
    card.fill.solid()
    card.fill.fore_color.rgb = CARD
    card.line.color.rgb = HAIRLINE
    card.line.width = Pt(1)
    card.shadow.inherit = False
    card.adjustments[0] = 0.04

    inset = Inches(0.4)
    tf = textbox(s, x + inset, card_top + Inches(0.4),
                 col_w - 2 * inset, Inches(0.45))
    write(tf, num, Pt(15), ACCENT, bold=True, align=PP_ALIGN.LEFT, first=True)

    tf = textbox(s, x + inset, card_top + Inches(1.05),
                 col_w - 2 * inset, Inches(1.5))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    p.line_spacing = 1.3
    for text, font, color in (
        (prefix + " " if prefix else "", FONT, INK),
        (code, MONO, ACCENT),
        (plain, FONT, INK),
    ):
        if not text:
            continue
        run = p.add_run()
        run.text = text
        run.font.name = font
        run.font.size = STEP
        run.font.color.rgb = color

footer(s, 4)

# ---------------------------------------------------------------- 5. Call to action

s = new_slide()
slide_title(s, "Install Marrow")

chip_w, chip_h = Inches(5.4), Inches(1.15)
chip = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                          int((SLIDE_W - chip_w) / 2), Inches(3.15),
                          chip_w, chip_h)
chip.fill.solid()
chip.fill.fore_color.rgb = CARD
chip.line.color.rgb = ACCENT
chip.line.width = Pt(1.25)
chip.shadow.inherit = False
chip.adjustments[0] = 0.16

tf = chip.text_frame
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
write(tf, "pipx install marrow", Pt(28), INK, bold=True, font=MONO, first=True)

tf = textbox(s, MARGIN, Inches(4.72), CONTENT_W, Inches(0.5))
write(tf, "Works with pytest, Jest, go test.", LEAD, MUTED, first=True)
footer(s, 5)

# ---------------------------------------------------------------- save

prs.save("deck.pptx")
print(f"Wrote deck.pptx — {len(prs.slides)} slides")
