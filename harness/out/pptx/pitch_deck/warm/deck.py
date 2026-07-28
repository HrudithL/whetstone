"""Build the 5-slide "Marrow" pitch deck (square 10x10 format, Consolas type)."""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# --- design tokens ---------------------------------------------------------
FONT = "Consolas"
BG = RGBColor(0xF7, 0xF6, 0xF3)      # warm off-white
INK = RGBColor(0x1E, 0x1E, 0x1E)     # near-black text
MUTED = RGBColor(0x6B, 0x67, 0x62)   # secondary text
ACCENT = RGBColor(0xC2, 0x41, 0x0C)  # burnt orange

HERO_SIZE = Pt(76)
TITLE_SIZE = Pt(38)
BODY_SIZE = Pt(20)
SMALL_SIZE = Pt(15)

MARGIN = Inches(0.9)
CONTENT_W = Inches(10) - 2 * MARGIN


def new_slide(prs):
    """Blank slide with the deck background."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = BG
    return slide


def textbox(slide, top, height, left=MARGIN, width=CONTENT_W):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    return tf


def write(tf, lines, size, color=INK, align=PP_ALIGN.CENTER, bold=False,
          space_after=Pt(0), line_spacing=1.15, first=False):
    """Append paragraphs of text, every run set in Consolas."""
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if (first and i == 0) else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        p.space_after = space_after
        run = p.add_run()
        run.text = line
        run.font.name = FONT
        run.font.size = size
        run.font.bold = bold
        run.font.color.rgb = color
    return tf


def rule(slide, top, width=Inches(1.6), height=Pt(4), color=ACCENT,
         left=None):
    """Thin accent rule, centered by default."""
    if left is None:
        left = (Inches(10) - width) // 2
    bar = slide.shapes.add_shape(1, left, top, width, height)  # rectangle
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def title_block(slide, text, eyebrow=None):
    """Top-aligned, centered slide title with an optional eyebrow label."""
    top = Inches(1.1)
    if eyebrow:
        tf = textbox(slide, top, Inches(0.4))
        write(tf, [eyebrow], SMALL_SIZE, ACCENT, first=True)
        top += Inches(0.55)
    tf = textbox(slide, top, Inches(2.0))
    write(tf, [text], TITLE_SIZE, INK, bold=True, line_spacing=1.1, first=True)


# --- deck ------------------------------------------------------------------
prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(10)

# 1 — Title
s = new_slide(prs)
tf = textbox(s, Inches(3.5), Inches(1.6))
write(tf, ["Marrow"], HERO_SIZE, INK, bold=True, first=True)
rule(s, Inches(5.35))
tf = textbox(s, Inches(5.95), Inches(1.0))
write(tf, ["Know what your tests actually cover."], BODY_SIZE, MUTED, first=True)

# 2 — The problem
s = new_slide(prs)
title_block(s, "Big test suites hide their gaps.", eyebrow="THE PROBLEM")
rule(s, Inches(3.5), width=Inches(1.2))
tf = textbox(s, Inches(4.3), Inches(3.0), left=Inches(1.4),
             width=Inches(10) - 2 * Inches(1.4))
write(tf, ["Large suites are slow, and nobody knows which tests cover which code."],
      BODY_SIZE, INK, line_spacing=1.4, first=True)
write(tf, ["So dead tests linger — and real gaps go unnoticed."],
      BODY_SIZE, MUTED, line_spacing=1.4, space_after=Pt(0))
tf.paragraphs[1].space_before = Pt(26)

# 3 — The idea
s = new_slide(prs)
title_block(s, "Watch one run.\nDraw the real map.", eyebrow="THE IDEA")
rule(s, Inches(4.2), width=Inches(1.2))
tf = textbox(s, Inches(5.0), Inches(2.4), left=Inches(1.4),
             width=Inches(10) - 2 * Inches(1.4))
write(tf, ["Marrow instruments a single test run and produces a test→code coverage map."],
      BODY_SIZE, INK, line_spacing=1.4, first=True)
tf2 = textbox(s, Inches(6.9), Inches(0.6))
write(tf2, ["No annotations. No config."], BODY_SIZE, ACCENT, bold=True, first=True)

# 4 — How it works
s = new_slide(prs)
title_block(s, "How it works", eyebrow="THREE STEPS")
rule(s, Inches(3.2), width=Inches(1.2))

steps = [
    ("01", "Run", "marrow watch -- <your test cmd>"),
    ("02", "Record", "Marrow records which lines each test exercised."),
    ("03", "Map", "It emits an interactive map plus a list of dead tests\nand untested lines."),
]
top = Inches(4.0)
for num, label, detail in steps:
    n = textbox(s, top, Inches(0.5), left=Inches(1.1), width=Inches(0.9))
    write(n, [num], BODY_SIZE, ACCENT, align=PP_ALIGN.LEFT, bold=True, first=True)
    body = textbox(s, top, Inches(1.5), left=Inches(2.1),
                   width=Inches(10) - Inches(2.1) - Inches(1.1))
    write(body, [label], BODY_SIZE, INK, align=PP_ALIGN.LEFT, bold=True, first=True)
    write(body, [detail], SMALL_SIZE, MUTED, align=PP_ALIGN.LEFT, line_spacing=1.35)
    body.paragraphs[1].space_before = Pt(6)
    top += Inches(1.55)

# 5 — Call to action
s = new_slide(prs)
tf = textbox(s, Inches(3.1), Inches(1.2))
write(tf, ["Install Marrow"], TITLE_SIZE, INK, bold=True, first=True)
rule(s, Inches(4.35), width=Inches(1.6))

card_w, card_h = Inches(6.4), Inches(1.25)
card = s.shapes.add_shape(1, (Inches(10) - card_w) // 2, Inches(5.1), card_w, card_h)
card.fill.solid()
card.fill.fore_color.rgb = RGBColor(0xEC, 0xE8, 0xE1)
card.line.color.rgb = ACCENT
card.line.width = Pt(1.25)
card.shadow.inherit = False
ctf = card.text_frame
ctf.word_wrap = True
ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
write(ctf, ["pipx install marrow"], Pt(28), INK, bold=True, first=True)

tf = textbox(s, Inches(6.9), Inches(0.7))
write(tf, ["Works with pytest, Jest, go test."], BODY_SIZE, MUTED, first=True)

prs.save("deck.pptx")
print("wrote deck.pptx")
