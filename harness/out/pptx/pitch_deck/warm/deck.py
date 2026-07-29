"""Build the 5-slide "Marrow" pitch deck (square 1:1, Consolas throughout)."""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# --- design tokens -----------------------------------------------------------

FONT = "Consolas"

BG = RGBColor(0xF6, 0xF5, 0xF2)        # warm off-white page
INK = RGBColor(0x1B, 0x1B, 0x1E)       # near-black text
MUTED = RGBColor(0x6B, 0x6B, 0x73)     # secondary text
ACCENT = RGBColor(0xC2, 0x41, 0x0C)    # burnt orange
PANEL = RGBColor(0x1B, 0x1B, 0x1E)     # dark code panel
PANEL_TEXT = RGBColor(0xF6, 0xF5, 0xF2)

SIDE = Inches(0.95)                    # left/right margin
CONTENT_W = Inches(10) - 2 * SIDE

TITLE_PT = 30   # Consolas is wide; keeps the longest title on one line
LEAD_PT = 20
BODY_PT = 16
CODE_PT = 15
SMALL_PT = 10.5

prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(10)
BLANK = prs.slide_layouts[6]


# --- helpers -----------------------------------------------------------------

def add_slide():
    """Blank slide painted with the deck background."""
    slide = prs.slides.add_slide(BLANK)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
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


def write(tf, lines, size, color=INK, bold=False, align=PP_ALIGN.LEFT,
          space_after=0, line_spacing=1.25, first=None):
    """Fill a text frame; every run is set to Consolas."""
    for i, text in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        run = p.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        if i == 0 and first:
            run.font.size = Pt(first.get("size", size))
            run.font.bold = first.get("bold", bold)
            run.font.color.rgb = first.get("color", color)
    return tf


def rule(slide, top, width=Inches(1.5), color=ACCENT, thickness=Pt(3.5), left=SIDE):
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, thickness)
    line.fill.solid()
    line.fill.fore_color.rgb = color
    line.line.fill.background()
    line.shadow.inherit = False
    return line


def panel(slide, top, height, color=PANEL, left=SIDE, width=CONTENT_W):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = color
    box.line.fill.background()
    box.shadow.inherit = False
    box.adjustments[0] = 0.08
    return box


def slide_title(slide, text):
    """Section title: top-aligned, centered, with an accent rule beneath."""
    tf = textbox(slide, SIDE, Inches(1.0), CONTENT_W, Inches(1.4))
    write(tf, [text], TITLE_PT, INK, bold=True, align=PP_ALIGN.CENTER, line_spacing=1.1)
    rule(slide, Inches(2.05), width=Inches(1.6),
         left=int((prs.slide_width - Inches(1.6)) / 2))


def footer(slide, label, number):
    tf = textbox(slide, SIDE, Inches(9.15), CONTENT_W, Inches(0.4))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    for text, color in ((label, MUTED), ("   ·   ", MUTED), (number, ACCENT)):
        run = p.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = Pt(SMALL_PT)
        run.font.color.rgb = color


# --- 1. title ----------------------------------------------------------------

s = add_slide()
tf = textbox(s, SIDE, Inches(3.5), CONTENT_W, Inches(1.6))
write(tf, ["Marrow"], 76, INK, bold=True, align=PP_ALIGN.CENTER, line_spacing=1.0)

rule(s, Inches(4.95), width=Inches(2.2), left=int((prs.slide_width - Inches(2.2)) / 2))

tf = textbox(s, SIDE, Inches(5.5), CONTENT_W, Inches(0.8))
write(tf, ["Know what your tests actually cover."], LEAD_PT, MUTED,
      align=PP_ALIGN.CENTER)

tf = textbox(s, SIDE, Inches(6.4), CONTENT_W, Inches(0.5))
write(tf, ["$ marrow watch -- pytest"], CODE_PT, ACCENT, align=PP_ALIGN.CENTER)

tf = textbox(s, SIDE, Inches(9.15), CONTENT_W, Inches(0.4))
write(tf, ["a CLI that maps tests to the code they cover"], SMALL_PT, MUTED,
      align=PP_ALIGN.CENTER)


# --- 2. the problem ----------------------------------------------------------

s = add_slide()
slide_title(s, "Big test suites hide their gaps.")
footer(s, "the problem", "02")

tf = textbox(s, SIDE, Inches(3.1), CONTENT_W, Inches(3.0))
write(tf, [
    "Large suites are slow, and nobody knows",
    "which tests cover which code.",
], LEAD_PT, INK, line_spacing=1.35, space_after=20)

items = [
    ("Dead tests linger.", "They pass forever and guard nothing."),
    ("Real gaps go unnoticed.", "A green run says little about coverage."),
    ("Slow feedback.", "Everything runs because nothing is mapped."),
]
top = Inches(4.6)
for head, sub in items:
    rule(s, top + Inches(0.12), width=Inches(0.22), thickness=Pt(9), left=SIDE)
    tf = textbox(s, SIDE + Inches(0.55), top, CONTENT_W - Inches(0.55), Inches(1.0))
    write(tf, [head], BODY_PT, INK, bold=True, line_spacing=1.2)
    tf2 = textbox(s, SIDE + Inches(0.55), top + Inches(0.34),
                  CONTENT_W - Inches(0.55), Inches(0.6))
    write(tf2, [sub], BODY_PT, MUTED, line_spacing=1.2)
    top += Inches(1.15)


# --- 3. the idea -------------------------------------------------------------

s = add_slide()
slide_title(s, "Watch one run. Draw the real map.")
footer(s, "the idea", "03")

tf = textbox(s, SIDE, Inches(3.2), CONTENT_W, Inches(2.2))
write(tf, [
    "Marrow instruments a single test run and",
    "produces a test → code coverage map.",
], LEAD_PT, INK, line_spacing=1.35)

p = panel(s, Inches(5.2), Inches(2.1))
tf = p.text_frame
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
tf.margin_left = tf.margin_right = Inches(0.5)
write(tf, [
    "no annotations",
    "no config",
    "one run, the whole map",
], LEAD_PT, PANEL_TEXT, align=PP_ALIGN.CENTER, line_spacing=1.45)
tf.paragraphs[1].runs[0].font.color.rgb = PANEL_TEXT
tf.paragraphs[2].runs[0].font.color.rgb = ACCENT
tf.paragraphs[2].runs[0].font.bold = True

tf = textbox(s, SIDE, Inches(7.8), CONTENT_W, Inches(0.6))
write(tf, ["Point it at the test command you already use."], BODY_PT, MUTED,
      align=PP_ALIGN.CENTER)


# --- 4. how it works ---------------------------------------------------------

s = add_slide()
slide_title(s, "How it works")
footer(s, "how it works", "04")

steps = [
    ("01", "Run it", "marrow watch -- <your test cmd>", True),
    ("02", "It records", "which lines each test exercised", False),
    ("03", "It emits", "an interactive map + dead tests + untested lines", False),
]

top = Inches(3.2)
for num, head, detail, is_code in steps:
    tf = textbox(s, SIDE, top, Inches(1.0), Inches(0.8))
    write(tf, [num], 30, ACCENT, bold=True, line_spacing=1.0)

    tf = textbox(s, SIDE + Inches(1.1), top + Inches(0.05),
                 CONTENT_W - Inches(1.1), Inches(0.5))
    write(tf, [head], LEAD_PT, INK, bold=True, line_spacing=1.15)

    if is_code:
        box = panel(s, top + Inches(0.6), Inches(0.62),
                    left=SIDE + Inches(1.1), width=CONTENT_W - Inches(1.1))
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.3)
        p = tf.paragraphs[0]
        for text, color in (("$ ", ACCENT), (detail, PANEL_TEXT)):
            run = p.add_run()
            run.text = text
            run.font.name = FONT
            run.font.size = Pt(CODE_PT)
            run.font.color.rgb = color
    else:
        tf = textbox(s, SIDE + Inches(1.1), top + Inches(0.62),
                     CONTENT_W - Inches(1.1), Inches(0.8))
        write(tf, [detail], BODY_PT, MUTED, line_spacing=1.3)

    top += Inches(1.8)

rule(s, Inches(8.6), width=CONTENT_W, thickness=Pt(1.5), color=RGBColor(0xDD, 0xDA, 0xD3))


# --- 5. call to action -------------------------------------------------------

s = add_slide()
slide_title(s, "Install Marrow")
footer(s, "get started", "05")

box = panel(s, Inches(4.0), Inches(1.5))
tf = box.text_frame
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
for text, color in (("$ ", ACCENT), ("pipx install marrow", PANEL_TEXT)):
    run = p.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(27)
    run.font.bold = True
    run.font.color.rgb = color

tf = textbox(s, SIDE, Inches(6.1), CONTENT_W, Inches(0.7))
write(tf, ["Works with pytest, Jest, go test."], LEAD_PT, INK,
      align=PP_ALIGN.CENTER)

rule(s, Inches(7.1), width=Inches(1.6), left=int((prs.slide_width - Inches(1.6)) / 2))

tf = textbox(s, SIDE, Inches(7.6), CONTENT_W, Inches(0.6))
write(tf, ["Know what your tests actually cover."], BODY_PT, MUTED,
      align=PP_ALIGN.CENTER)

prs.save("deck.pptx")
print(f"wrote deck.pptx — {len(prs.slides.__iter__.__self__._sldIdLst)} slides, "
      f"{prs.slide_width.inches:g}x{prs.slide_height.inches:g} in")
