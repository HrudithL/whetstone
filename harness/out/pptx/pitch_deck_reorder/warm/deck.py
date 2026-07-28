"""Build the Marrow pitch deck (deck.pptx) with python-pptx."""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# ---------------------------------------------------------------- design system

BG = RGBColor(0xFA, 0xF9, 0xF6)        # warm off-white
INK = RGBColor(0x1A, 0x1A, 0x1A)       # near-black body/title text
MUTED = RGBColor(0x6B, 0x6B, 0x66)     # secondary text
ACCENT = RGBColor(0xC2, 0x41, 0x0C)    # burnt orange
ACCENT_INK = RGBColor(0xFF, 0xF6, 0xEE)  # text on accent background

SANS = "Arial"
MONO = "Consolas"

TITLE_PT = 40
HERO_PT = 72
SUB_PT = 22
BODY_PT = 20
STEP_PT = 19
CODE_PT = 24

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(1.0)
CONTENT_W = SLIDE_W - 2 * MARGIN

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers

def add_slide(bg=BG):
    slide = prs.slides.add_slide(BLANK)
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = bg
    return slide


def textbox(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def write(tf, text, *, size, color=INK, font=SANS, bold=False,
          align=PP_ALIGN.CENTER, space_after=0, space_before=0,
          line_spacing=1.15, first=False):
    """Write a paragraph into a text frame, styled."""
    para = tf.paragraphs[0] if first else tf.add_paragraph()
    para.alignment = align
    para.space_after = Pt(space_after)
    para.space_before = Pt(space_before)
    para.line_spacing = line_spacing
    run = para.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return para


def rule(slide, top, width=Inches(1.4), color=ACCENT, height=Pt(4.5)):
    """Short centered accent rule."""
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, int((SLIDE_W - width) / 2), int(top), int(width), int(height)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def slide_title(slide, text, *, color=INK, rule_color=ACCENT):
    """Top-aligned, centered title with an accent rule beneath it."""
    tf = textbox(slide, MARGIN, Inches(0.85), CONTENT_W, Inches(1.0))
    write(tf, text, size=TITLE_PT, color=color, bold=True, first=True)
    rule(slide, Inches(1.85), color=rule_color)


# ---------------------------------------------------------------- 1. Title

s = add_slide()
tf = textbox(s, MARGIN, Inches(2.45), CONTENT_W, Inches(1.6))
write(tf, "Marrow", size=HERO_PT, bold=True, first=True)
rule(s, Inches(4.05), width=Inches(2.0))
tf = textbox(s, MARGIN, Inches(4.55), CONTENT_W, Inches(0.9))
write(tf, "Know what your tests actually cover.",
      size=SUB_PT, color=MUTED, first=True)


# ---------------------------------------------------------------- 2. Call to action

s = add_slide(bg=ACCENT)
slide_title(s, "Install Marrow", color=ACCENT_INK, rule_color=ACCENT_INK)

# command chip
chip_w, chip_h = Inches(6.4), Inches(1.35)
chip = s.shapes.add_shape(
    MSO_SHAPE.ROUNDED_RECTANGLE, int((SLIDE_W - chip_w) / 2), int(Inches(2.85)), int(chip_w), int(chip_h)
)
chip.fill.solid()
chip.fill.fore_color.rgb = RGBColor(0x8C, 0x2D, 0x07)
chip.line.fill.background()
chip.shadow.inherit = False
ctf = chip.text_frame
ctf.word_wrap = True
ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
write(ctf, "pipx install marrow", size=CODE_PT, color=ACCENT_INK,
      font=MONO, bold=True, first=True)

tf = textbox(s, MARGIN, Inches(4.75), CONTENT_W, Inches(1.0))
write(tf, "Works with pytest, Jest, go test.",
      size=BODY_PT, color=ACCENT_INK, first=True)


# ---------------------------------------------------------------- 3. The problem

s = add_slide()
slide_title(s, "Big test suites hide their gaps.")
tf = textbox(s, Inches(2.0), Inches(2.85), SLIDE_W - Inches(4.0), Inches(2.4))
write(tf, "Large suites are slow, and nobody knows which tests cover which code.",
      size=BODY_PT, first=True, line_spacing=1.35)
write(tf, "So dead tests linger, and real gaps go unnoticed.",
      size=BODY_PT, color=MUTED, space_before=18, line_spacing=1.35)


# ---------------------------------------------------------------- 4. The idea

s = add_slide()
slide_title(s, "Watch one run. Draw the real map.")
tf = textbox(s, Inches(2.0), Inches(2.85), SLIDE_W - Inches(4.0), Inches(2.4))
write(tf, "Marrow instruments a single test run and produces a test → code coverage map.",
      size=BODY_PT, first=True, line_spacing=1.35)
write(tf, "No annotations. No config.",
      size=BODY_PT, color=ACCENT, bold=True, space_before=18, line_spacing=1.35)


# ---------------------------------------------------------------- 5. Why now

s = add_slide()
slide_title(s, "Why now")
tf = textbox(s, Inches(2.0), Inches(2.85), SLIDE_W - Inches(4.0), Inches(2.6))
write(tf, "Test suites have outgrown the humans maintaining them.",
      size=BODY_PT, bold=True, first=True, line_spacing=1.35)
write(tf, "Thousands of tests, years of turnover, no one left who remembers what each "
          "one was for. Tracking coverage by hand stopped being realistic a long time ago.",
      size=BODY_PT, color=MUTED, space_before=18, line_spacing=1.35)


# ---------------------------------------------------------------- 6. How it works

s = add_slide()
slide_title(s, "How it works")

steps = [
    ("1", "Run it", "marrow watch -- <your test cmd>", True),
    ("2", "It records", "Which lines each test actually exercised.", False),
    ("3", "It maps", "An interactive map, plus dead tests and untested lines.", False),
]

col_w = Inches(3.5)
gap = Inches(0.55)
total_w = 3 * col_w + 2 * gap
left0 = int((SLIDE_W - total_w) / 2)
top = Inches(2.75)

for i, (num, heading, detail, is_code) in enumerate(steps):
    left = left0 + i * int(col_w + gap)

    dot_d = Inches(0.62)
    dot = s.shapes.add_shape(
        MSO_SHAPE.OVAL, left + int((col_w - dot_d) / 2), int(top), int(dot_d), int(dot_d)
    )
    dot.fill.solid()
    dot.fill.fore_color.rgb = ACCENT
    dot.line.fill.background()
    dot.shadow.inherit = False
    dtf = dot.text_frame
    dtf.vertical_anchor = MSO_ANCHOR.MIDDLE
    write(dtf, num, size=20, color=ACCENT_INK, bold=True, first=True)

    tf = textbox(s, left, top + Inches(0.95), col_w, Inches(2.2))
    write(tf, heading, size=BODY_PT, bold=True, first=True)
    write(tf, detail,
          size=CODE_PT - 8 if is_code else STEP_PT,
          color=ACCENT if is_code else MUTED,
          font=MONO if is_code else SANS,
          space_before=12, line_spacing=1.3)


prs.save("deck.pptx")
print(f"Wrote deck.pptx - {len(prs.slides)} slides")
