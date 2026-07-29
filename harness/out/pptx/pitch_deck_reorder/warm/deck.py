"""Build the Marrow pitch deck (deck.pptx) with python-pptx.

Slide order:
  1. Title
  2. Call to action  -- "Install Marrow" leads the deck, right after the title
  3. The problem
  4. The idea
  5. Why now         -- makes the case that manual coverage tracking is untenable
  6. How it works
"""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

# ---------------------------------------------------------------- design system
FONT = "Helvetica Neue"
MONO = "Menlo"

BG = RGBColor(0xF7, 0xF6, 0xF3)      # warm paper
INK = RGBColor(0x1A, 0x1A, 0x1A)     # near-black text
MUTED = RGBColor(0x5F, 0x5C, 0x57)   # secondary text
ACCENT = RGBColor(0x0F, 0x7A, 0x6C)  # single accent: teal

TITLE_SIZE = Pt(44)
HERO_SIZE = Pt(76)
BODY_SIZE = Pt(22)
LEAD_SIZE = Pt(28)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(1.1)
CONTENT_W = SLIDE_W - 2 * MARGIN

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


def new_slide():
    """Blank slide with the deck background."""
    slide = prs.slides.add_slide(BLANK)
    bg = slide.shapes.add_shape(1, 0, 0, SLIDE_W, SLIDE_H)  # 1 = rectangle
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    return slide


def textbox(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def style(run, size, color=INK, bold=False, font=FONT):
    run.font.name = font
    run.font.size = size
    run.font.color.rgb = color
    run.font.bold = bold


def para(tf, text, size, color=INK, bold=False, font=FONT,
         align=PP_ALIGN.LEFT, space_after=Pt(0), space_before=Pt(0), first=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = space_after
    p.space_before = space_before
    p.line_spacing = 1.15
    style(p.add_run(), size, color, bold, font)
    p.runs[0].text = text
    return p


def accent_rule(slide, top, left=MARGIN, width=Inches(1.6)):
    """Short accent bar that sits under a slide title."""
    bar = slide.shapes.add_shape(1, left, top, width, Pt(5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def section_title(slide, title):
    """Centered, top-aligned slide title with a centered accent rule."""
    tf = textbox(slide, MARGIN, Inches(0.85), CONTENT_W, Inches(1.1))
    para(tf, title, TITLE_SIZE, INK, bold=True, align=PP_ALIGN.CENTER, first=True)
    accent_rule(slide, Inches(2.05), left=(SLIDE_W - Inches(1.6)) // 2)


# ------------------------------------------------------------------- 1. Title
s = new_slide()
tf = textbox(s, MARGIN, Inches(2.5), CONTENT_W, Inches(1.9))
para(tf, "Marrow", HERO_SIZE, INK, bold=True, align=PP_ALIGN.CENTER, first=True)
accent_rule(s, Inches(4.15), left=(SLIDE_W - Inches(2.2)) // 2, width=Inches(2.2))
tf = textbox(s, MARGIN, Inches(4.6), CONTENT_W, Inches(0.9))
para(tf, "Know what your tests actually cover.", LEAD_SIZE, MUTED,
     align=PP_ALIGN.CENTER, first=True)

# ----------------------------------------------- 2. Call to action (leads deck)
s = new_slide()
section_title(s, "Install Marrow")

cmd = s.shapes.add_shape(1, Inches(3.4), Inches(3.0), Inches(6.533), Inches(1.3))
cmd.fill.solid()
cmd.fill.fore_color.rgb = RGBColor(0xEC, 0xEA, 0xE4)
cmd.line.color.rgb = ACCENT
cmd.line.width = Pt(1.5)
cmd.shadow.inherit = False
ctf = cmd.text_frame
ctf.word_wrap = True
ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
para(ctf, "pipx install marrow", Pt(34), INK, bold=True, font=MONO,
     align=PP_ALIGN.CENTER, first=True)

tf = textbox(s, MARGIN, Inches(4.75), CONTENT_W, Inches(0.9))
para(tf, "Works with pytest, Jest, go test.", LEAD_SIZE, ACCENT,
     align=PP_ALIGN.CENTER, first=True)

# ------------------------------------------------------------- 3. The problem
s = new_slide()
section_title(s, "Big test suites hide their gaps.")
tf = textbox(s, MARGIN + Inches(0.9), Inches(3.0), CONTENT_W - Inches(1.8), Inches(2.6))
for i, line in enumerate([
    "Large suites are slow, and nobody knows which tests cover which code.",
    "Dead tests linger for years, quietly costing minutes on every run.",
    "Real gaps go unnoticed until something breaks in production.",
]):
    para(tf, line, BODY_SIZE, INK if i == 0 else MUTED,
         space_after=Pt(20), first=(i == 0))

# ----------------------------------------------------------------- 4. The idea
s = new_slide()
section_title(s, "Watch one run. Draw the real map.")
tf = textbox(s, MARGIN + Inches(0.9), Inches(3.1), CONTENT_W - Inches(1.8), Inches(2.4))
para(tf, "Marrow instruments a single test run and produces a test→code "
         "coverage map.", LEAD_SIZE, INK, first=True, space_after=Pt(26))
para(tf, "No annotations. No config. No rewriting your suite.", BODY_SIZE, ACCENT)

# ------------------------------------------------------------------ 5. Why now
s = new_slide()
section_title(s, "Why now")
tf = textbox(s, MARGIN + Inches(0.9), Inches(2.95), CONTENT_W - Inches(1.8), Inches(3.0))
para(tf, "Test suites have outgrown the humans who maintain them.", LEAD_SIZE,
     INK, first=True, space_after=Pt(24))
for line in [
    "A modern repo ships thousands of tests across years of contributors.",
    "Coverage percentages say how much code is covered — never by which test.",
    "Tracking that map by hand stopped being possible; it has to be measured.",
]:
    para(tf, line, BODY_SIZE, MUTED, space_after=Pt(16))

# --------------------------------------------------------------- 6. How it works
s = new_slide()
section_title(s, "How it works")

steps = [
    ("1", "Run it", "marrow watch -- <your test cmd>", True),
    ("2", "Marrow records", "which lines each test exercised", False),
    ("3", "You get a map", "interactive map + dead tests + untested lines", False),
]
col_w = Inches(3.5)
gap = Inches(0.55)
total = 3 * col_w + 2 * gap
left0 = (SLIDE_W - total) // 2

for i, (num, head, detail, is_code) in enumerate(steps):
    left = left0 + i * (col_w + gap)
    ntf = textbox(s, left, Inches(2.85), col_w, Inches(0.7))
    para(ntf, num, Pt(40), ACCENT, bold=True, align=PP_ALIGN.CENTER, first=True)
    htf = textbox(s, left, Inches(3.7), col_w, Inches(0.5))
    para(htf, head, Pt(24), INK, bold=True, align=PP_ALIGN.CENTER, first=True)
    dtf = textbox(s, left, Inches(4.35), col_w, Inches(1.5))
    para(dtf, detail, Pt(16) if is_code else Pt(18), MUTED,
         font=MONO if is_code else FONT, align=PP_ALIGN.CENTER, first=True)

prs.save("deck.pptx")
print("wrote deck.pptx with %d slides" % len(prs.slides._sldIdLst))
