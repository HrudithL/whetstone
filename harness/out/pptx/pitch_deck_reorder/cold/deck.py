from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ----- Palette -----
BG = RGBColor(0x12, 0x16, 0x1C)        # deep slate background
TEXT = RGBColor(0xE8, 0xEC, 0xF1)      # near-white text
MUTED = RGBColor(0x9A, 0xA6, 0xB2)     # muted gray for secondary text
ACCENT = RGBColor(0xF2, 0x6B, 0x3A)    # warm orange accent
PANEL = RGBColor(0x1B, 0x22, 0x2B)     # slightly lighter panel

FONT = "Arial"

# ----- Setup: 16:9 -----
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def add_slide():
    slide = prs.slides.add_slide(BLANK)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    slide.shapes._spTree.remove(bg._element)
    slide.shapes._spTree.insert(2, bg._element)
    return slide


def accent_bar(slide, left, top, w=Inches(0.9), h=Inches(0.09)):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, w, h)
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def textbox(slide, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    return tf


def style(para, text, size, color, bold=False, align=PP_ALIGN.LEFT,
          font=FONT, space_after=None, space_before=None):
    para.alignment = align
    if space_after is not None:
        para.space_after = space_after
    if space_before is not None:
        para.space_before = space_before
    run = para.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return run


# =========================================================
# Slide 1 — Title
# =========================================================
s = add_slide()
accent_bar(s, Inches(1.0), Inches(2.55), w=Inches(1.4), h=Inches(0.12))
tf = textbox(s, Inches(1.0), Inches(2.75), Inches(11.3), Inches(2.4))
style(tf.paragraphs[0], "Marrow", 88, TEXT, bold=True)
p = tf.add_paragraph()
style(p, "Know what your tests actually cover.", 30, MUTED, space_before=Pt(14))

# =========================================================
# Slide 2 — The problem
# =========================================================
s = add_slide()
accent_bar(s, Inches(1.0), Inches(1.1))
tf = textbox(s, Inches(1.0), Inches(1.45), Inches(11.3), Inches(1.4))
style(tf.paragraphs[0], "Big test suites hide their gaps.", 44, TEXT, bold=True)

tf = textbox(s, Inches(1.0), Inches(3.2), Inches(10.8), Inches(3.0))
lines = [
    "Large suites are slow to run.",
    "Nobody knows which tests cover which code.",
    "Dead tests linger, and real gaps go unnoticed.",
]
for i, t in enumerate(lines):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = style(p, "—  ", 26, ACCENT, bold=True, space_after=Pt(16))
    run = p.add_run()
    run.text = t
    run.font.name = FONT
    run.font.size = Pt(26)
    run.font.color.rgb = TEXT

# =========================================================
# Slide 3 — The idea
# =========================================================
s = add_slide()
accent_bar(s, Inches(1.0), Inches(1.1))
tf = textbox(s, Inches(1.0), Inches(1.45), Inches(11.3), Inches(2.2))
style(tf.paragraphs[0], "Watch one run.", 52, TEXT, bold=True)
p = tf.add_paragraph()
style(p, "Draw the real map.", 52, ACCENT, bold=True)

tf = textbox(s, Inches(1.0), Inches(4.35), Inches(10.6), Inches(2.2))
style(tf.paragraphs[0],
      "Marrow instruments a single test run and produces a "
      "test → code coverage map.", 26, TEXT, space_after=Pt(10))
p = tf.add_paragraph()
style(p, "No annotations. No config.", 24, MUTED)

# =========================================================
# Slide 4 — How it works
# =========================================================
s = add_slide()
accent_bar(s, Inches(1.0), Inches(1.1))
tf = textbox(s, Inches(1.0), Inches(1.45), Inches(11.3), Inches(1.2))
style(tf.paragraphs[0], "How it works", 44, TEXT, bold=True)

steps = [
    ("1", "Run", "marrow watch -- <your test cmd>", True),
    ("2", "Record", "Marrow records which lines each test exercised.", False),
    ("3", "Map", "It emits an interactive map plus a list of dead "
                 "tests and untested lines.", False),
]
col_w = Inches(3.6)
gap = Inches(0.35)
start_x = Inches(1.0)
top = Inches(3.1)
h = Inches(3.0)
for i, (num, head, body, mono) in enumerate(steps):
    x = start_x + (col_w + gap) * i
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, col_w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = PANEL
    card.line.color.rgb = ACCENT
    card.line.width = Pt(1.0)
    card.shadow.inherit = False

    tf = textbox(s, x + Inches(0.35), top + Inches(0.3),
                 col_w - Inches(0.7), h - Inches(0.6))
    style(tf.paragraphs[0], num, 40, ACCENT, bold=True, space_after=Pt(6))
    p = tf.add_paragraph()
    style(p, head, 24, TEXT, bold=True, space_after=Pt(12))
    p = tf.add_paragraph()
    if mono:
        r = style(p, body, 16, TEXT, font="Courier New")
    else:
        style(p, body, 18, MUTED)

# =========================================================
# Slide 5 — Call to action
# =========================================================
s = add_slide()
accent_bar(s, Inches(1.0), Inches(2.35), w=Inches(1.4), h=Inches(0.12))
tf = textbox(s, Inches(1.0), Inches(2.6), Inches(11.3), Inches(1.2))
style(tf.paragraphs[0], "Install Marrow", 60, TEXT, bold=True)

# command chip
chip = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                          Inches(1.0), Inches(3.95), Inches(5.2), Inches(0.95))
chip.fill.solid()
chip.fill.fore_color.rgb = PANEL
chip.line.color.rgb = ACCENT
chip.line.width = Pt(1.0)
chip.shadow.inherit = False
ctf = chip.text_frame
ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
ctf.margin_left = Inches(0.35)
style(ctf.paragraphs[0], "pipx install marrow", 28, TEXT, font="Courier New")

tf = textbox(s, Inches(1.0), Inches(5.35), Inches(11.3), Inches(0.8))
style(tf.paragraphs[0], "Works with pytest, Jest, go test.", 24, MUTED)

prs.save("deck.pptx")
print("Saved deck.pptx")
