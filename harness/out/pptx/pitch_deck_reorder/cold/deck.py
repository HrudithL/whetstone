"""Build the 5-slide "Marrow" pitch deck (deck.pptx) with python-pptx.

Design system
-------------
Slides   : 16:9, 13.333in x 7.5in
Palette  : warm off-white background, near-black ink, one rust accent
Type     : Arial throughout; titles 40pt (72pt on the title slide), body 20pt
Layout   : blank layouts + explicit text boxes; titles top-aligned and centered,
           with a short accent rule underneath.
"""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# --- palette ---------------------------------------------------------------
BG = RGBColor(0xFB, 0xFA, 0xF8)
INK = RGBColor(0x17, 0x18, 0x1A)
MUTED = RGBColor(0x5F, 0x63, 0x68)
ACCENT = RGBColor(0xB4, 0x53, 0x1F)
CHIP_BG = RGBColor(0xF1, 0xED, 0xE7)

# --- type ------------------------------------------------------------------
FONT = "Arial"
MONO = "Consolas"
SZ_WORDMARK = Pt(72)
SZ_TITLE = Pt(40)
SZ_LEAD = Pt(24)
SZ_BODY = Pt(20)
SZ_SMALL = Pt(16)

# --- geometry --------------------------------------------------------------
DECK_W = Inches(13.333)
DECK_H = Inches(7.5)
MARGIN = Inches(0.9)
CONTENT_W = DECK_W - 2 * MARGIN

prs = Presentation()
prs.slide_width = DECK_W
prs.slide_height = DECK_H
BLANK = prs.slide_layouts[6]


def new_slide():
    """A blank slide painted with the deck background color."""
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


def write(tf, text, size, color=INK, bold=False, align=PP_ALIGN.CENTER,
          font=FONT, space_after=0, line_spacing=1.15, first=False):
    """Add (or fill, if `first`) a paragraph with a single styled run."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    p.line_spacing = line_spacing
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = size
    run.font.bold = bold
    run.font.color.rgb = color
    return p


def accent_rule(slide, top, width=Inches(1.2), left=None):
    """The short rust rule that sits under every title."""
    left = (DECK_W - width) // 2 if left is None else left
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, Pt(4))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def title_block(slide, title):
    """Centered, top-aligned slide title + accent rule. Returns body top."""
    tf = textbox(slide, MARGIN, Inches(0.95), CONTENT_W, Inches(1.1))
    write(tf, title, SZ_TITLE, INK, bold=True, first=True)
    accent_rule(slide, Inches(2.15))
    return Inches(2.85)


# --- 1. Title --------------------------------------------------------------
slide = new_slide()
tf = textbox(slide, MARGIN, Inches(2.45), CONTENT_W, Inches(1.4))
write(tf, "Marrow", SZ_WORDMARK, INK, bold=True, first=True)
accent_rule(slide, Inches(4.05), width=Inches(1.6))
tf = textbox(slide, MARGIN, Inches(4.55), CONTENT_W, Inches(0.7))
write(tf, "Know what your tests actually cover.", SZ_LEAD, MUTED, first=True)

# --- 2. The problem --------------------------------------------------------
slide = new_slide()
top = title_block(slide, "Big test suites hide their gaps.")
tf = textbox(slide, Inches(2.15), top, DECK_W - 2 * Inches(2.15), Inches(2.6))
write(tf, "Large suites are slow, and nobody knows which tests cover "
          "which code.", SZ_BODY, INK, space_after=18, line_spacing=1.35,
      first=True)
write(tf, "So dead tests linger for years — and the real gaps go unnoticed.",
      SZ_BODY, MUTED, line_spacing=1.35)

# --- 3. The idea -----------------------------------------------------------
slide = new_slide()
top = title_block(slide, "Watch one run. Draw the real map.")
tf = textbox(slide, Inches(2.15), top, DECK_W - 2 * Inches(2.15), Inches(2.6))
write(tf, "Marrow instruments a single test run and produces a "
          "test → code coverage map.", SZ_BODY, INK, space_after=18,
      line_spacing=1.35, first=True)
write(tf, "No annotations. No config.", SZ_LEAD, ACCENT, bold=True)

# --- 4. How it works -------------------------------------------------------
slide = new_slide()
top = title_block(slide, "How it works")

STEPS = [
    ("01", "Run it", "marrow watch -- <your test cmd>", None),
    ("02", "It records", None,
     "Marrow records which lines each test exercised."),
    ("03", "It maps", None,
     "You get an interactive map, plus a list of dead tests and "
     "untested lines."),
]
gap = Inches(0.5)
col_w = (CONTENT_W - 2 * gap) // 3

for i, (num, label, code, body) in enumerate(STEPS):
    left = MARGIN + i * (col_w + gap)
    tf = textbox(slide, left, top, col_w, Inches(0.6))
    write(tf, num, Pt(30), ACCENT, bold=True, align=PP_ALIGN.LEFT, first=True)
    tf = textbox(slide, left, top + Inches(0.62), col_w, Inches(0.45))
    write(tf, label, SZ_BODY, INK, bold=True, align=PP_ALIGN.LEFT, first=True)

    body_top = top + Inches(1.2)
    if code:
        chip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left,
                                      body_top, col_w, Inches(1.1))
        chip.fill.solid()
        chip.fill.fore_color.rgb = CHIP_BG
        chip.line.fill.background()
        chip.shadow.inherit = False
        ctf = chip.text_frame
        ctf.word_wrap = True
        ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ctf.margin_left = ctf.margin_right = Inches(0.18)
        write(ctf, code, SZ_SMALL, ACCENT, align=PP_ALIGN.LEFT, font=MONO,
              first=True)
    else:
        tf = textbox(slide, left, body_top, col_w, Inches(1.8))
        write(tf, body, SZ_SMALL, MUTED, align=PP_ALIGN.LEFT,
              line_spacing=1.35, first=True)

# --- 5. Call to action -----------------------------------------------------
slide = new_slide()
top = title_block(slide, "Install Marrow")

chip_w = Inches(5.2)
chip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              (DECK_W - chip_w) // 2, top, chip_w, Inches(1.0))
chip.fill.solid()
chip.fill.fore_color.rgb = CHIP_BG
chip.line.fill.background()
chip.shadow.inherit = False
ctf = chip.text_frame
ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
write(ctf, "pipx install marrow", Pt(28), ACCENT, bold=True, font=MONO,
      first=True)

tf = textbox(slide, MARGIN, top + Inches(1.5), CONTENT_W, Inches(0.6))
write(tf, "Works with pytest, Jest, go test.", SZ_LEAD, MUTED, first=True)

prs.save("deck.pptx")
print("wrote deck.pptx")
