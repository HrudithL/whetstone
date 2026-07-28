"""Build the 5-slide "Marrow" pitch deck (deck.pptx) with python-pptx.

Design: 16:9, light background, dark text, a single rust accent.
One idea per slide; titles top-aligned and centered.
"""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------- design tokens

BG = RGBColor(0xF7, 0xF6, 0xF3)        # warm off-white page
INK = RGBColor(0x1A, 0x1A, 0x1F)       # near-black headline text
BODY = RGBColor(0x4A, 0x4A, 0x55)      # muted body text
MUTED = RGBColor(0x9A, 0x9A, 0xA4)     # captions, page numbers
ACCENT = RGBColor(0xC2, 0x41, 0x0C)    # rust — the one accent
CARD = RGBColor(0xFF, 0xFF, 0xFF)      # card fill
RULE = RGBColor(0xE3, 0xE0, 0xD9)      # hairline borders

FONT = "Arial"                          # one family, everywhere
MONO = "Consolas"                       # commands only

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.9)
CONTENT_W = SLIDE_W - 2 * MARGIN

TITLE_PT = 40
EYEBROW_PT = 13
BODY_PT = 20


# ---------------------------------------------------------------- helpers

def add_slide(prs):
    """Blank slide with the deck background painted in."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
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
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def write(tf, spans, size, color, bold=False, align=PP_ALIGN.CENTER,
          font=FONT, spacing=1.25, space_before=0, para=None):
    """Write one paragraph; `spans` is a string or list of (text, overrides)."""
    p = para if para is not None else (
        tf.paragraphs[0] if not tf.paragraphs[0].runs and not tf.paragraphs[0].text
        else tf.add_paragraph())
    p.alignment = align
    p.line_spacing = spacing
    p.space_before = Pt(space_before)
    if isinstance(spans, str):
        spans = [(spans, {})]
    for text, over in spans:
        run = p.add_run()
        run.text = text
        run.font.name = over.get("font", font)
        run.font.size = Pt(over.get("size", size))
        run.font.bold = over.get("bold", bold)
        run.font.color.rgb = over.get("color", color)
    return p


def eyebrow(slide, label):
    tf = textbox(slide, MARGIN, Inches(0.62), CONTENT_W, Inches(0.3))
    write(tf, label.upper(), EYEBROW_PT, ACCENT, bold=True, spacing=1.0)


def title(slide, text, top=Inches(1.12), size=TITLE_PT):
    tf = textbox(slide, MARGIN, top, CONTENT_W, Inches(1.5))
    write(tf, text, size, INK, bold=True, spacing=1.1)


def accent_rule(slide, top, width=Inches(1.1)):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, int((SLIDE_W - width) / 2), top, width, Pt(3.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False


def page_number(slide, n):
    tf = textbox(slide, SLIDE_W - MARGIN - Inches(1.0), SLIDE_H - Inches(0.72),
                 Inches(1.0), Inches(0.3))
    write(tf, f"{n}", 11, MUTED, align=PP_ALIGN.RIGHT, spacing=1.0)


# ---------------------------------------------------------------- slides

prs = Presentation()
prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H

# 1 — Title -------------------------------------------------------
s = add_slide(prs)
tf = textbox(s, MARGIN, Inches(2.45), CONTENT_W, Inches(1.6))
write(tf, "Marrow", 88, INK, bold=True, spacing=1.0)
accent_rule(s, Inches(4.12), Inches(1.4))
tf = textbox(s, MARGIN, Inches(4.6), CONTENT_W, Inches(0.9))
write(tf, "Know what your tests actually cover.", 26, BODY, spacing=1.2)
tf = textbox(s, MARGIN, Inches(6.35), CONTENT_W, Inches(0.35))
write(tf, "A CLI that maps a repo's tests to the code they cover", 13, MUTED,
      spacing=1.0)

# 2 — The problem -------------------------------------------------
s = add_slide(prs)
eyebrow(s, "The problem")
title(s, "Big test suites hide their gaps.")
accent_rule(s, Inches(2.35))
tf = textbox(s, Inches(2.15), Inches(3.05), SLIDE_W - 2 * Inches(2.15), Inches(2.2))
write(tf, "Large suites are slow, and nobody knows which tests cover which code.",
      BODY_PT + 4, BODY, spacing=1.35)
write(tf, "So dead tests linger for years — and the real gaps go unnoticed.",
      BODY_PT + 4, BODY, spacing=1.35, space_before=18)
page_number(s, 2)

# 3 — The idea ----------------------------------------------------
s = add_slide(prs)
eyebrow(s, "The idea")
title(s, "Watch one run. Draw the real map.")
accent_rule(s, Inches(2.35))
tf = textbox(s, Inches(2.15), Inches(3.05), SLIDE_W - 2 * Inches(2.15), Inches(2.2))
write(tf, "Marrow instruments a single test run and produces a "
          "test → code coverage map.", BODY_PT + 4, BODY, spacing=1.35)
write(tf, [("No annotations. No config.", {"color": ACCENT, "bold": True})],
      BODY_PT + 4, ACCENT, spacing=1.35, space_before=18)
page_number(s, 3)

# 4 — How it works ------------------------------------------------
s = add_slide(prs)
eyebrow(s, "How it works")
title(s, "Three steps, one command.")
accent_rule(s, Inches(2.35))

steps = [
    ("01", "Run your suite through Marrow.",
     [("marrow watch -- <your test cmd>", {"font": MONO, "size": 13,
                                           "color": ACCENT})]),
    ("02", "Marrow records the work.",
     [("It captures which lines each individual test exercised, as it runs.",
       {})]),
    ("03", "You get the map.",
     [("An interactive test → code map, plus a list of dead tests and "
       "untested lines.", {})]),
]

gap = Inches(0.4)
card_w = int((CONTENT_W - 2 * gap) / 3)
card_top, card_h = Inches(3.0), Inches(3.05)

for i, (num, heading, detail) in enumerate(steps):
    left = MARGIN + i * (card_w + gap)
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, card_top,
                              card_w, card_h)
    card.adjustments[0] = 0.055
    card.fill.solid()
    card.fill.fore_color.rgb = CARD
    card.line.color.rgb = RULE
    card.line.width = Pt(1)
    card.shadow.inherit = False

    pad = Inches(0.36)
    inner_w = card_w - 2 * pad
    tf = textbox(s, left + pad, card_top + Inches(0.4), inner_w, Inches(2.3))
    write(tf, num, 30, ACCENT, bold=True, align=PP_ALIGN.LEFT, spacing=1.0)
    write(tf, heading, 19, INK, bold=True, align=PP_ALIGN.LEFT, spacing=1.2,
          space_before=10)
    write(tf, detail, 15, BODY, align=PP_ALIGN.LEFT, spacing=1.3, space_before=10)

page_number(s, 4)

# 5 — Call to action ----------------------------------------------
s = add_slide(prs)
eyebrow(s, "Get started")
title(s, "Install Marrow.", top=Inches(1.35), size=48)

pill_w, pill_h = Inches(5.4), Inches(1.0)
pill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                          int((SLIDE_W - pill_w) / 2), Inches(3.15),
                          pill_w, pill_h)
pill.adjustments[0] = 0.22
pill.fill.solid()
pill.fill.fore_color.rgb = INK
pill.line.fill.background()
pill.shadow.inherit = False
tf = pill.text_frame
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
tf.margin_left = tf.margin_right = Emu(0)
write(tf, [("$ ", {"color": MUTED}), ("pipx install marrow", {})],
      24, RGBColor(0xFF, 0xFF, 0xFF), bold=True, font=MONO, spacing=1.0)

tf = textbox(s, MARGIN, Inches(4.75), CONTENT_W, Inches(0.6))
write(tf, "Works with pytest, Jest, and go test.", 22, BODY, spacing=1.2)
accent_rule(s, Inches(5.75), Inches(1.1))
page_number(s, 5)

prs.save("deck.pptx")
print("wrote deck.pptx")
