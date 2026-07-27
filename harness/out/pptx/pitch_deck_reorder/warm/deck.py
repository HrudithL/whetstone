"""Build the Marrow pitch deck and save it to deck.pptx."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# ----- Palette -----
BG = RGBColor(0x12, 0x16, 0x21)        # deep slate background
TEXT = RGBColor(0xE8, 0xEC, 0xF2)      # near-white body text
MUTED = RGBColor(0x9A, 0xA6, 0xB8)     # muted subtitle / captions
ACCENT = RGBColor(0x4F, 0xD1, 0xC5)    # teal accent

FONT = "Helvetica Neue"

# ----- Deck setup (16:9) -----
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def add_slide():
    slide = prs.slides.add_slide(BLANK)
    bg = slide.shapes.add_shape(
        1, 0, 0, SW, SH  # MSO_SHAPE.RECTANGLE
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    slide.shapes._spTree.remove(bg._element)
    slide.shapes._spTree.insert(2, bg._element)
    return slide


def accent_bar(slide, left=Inches(0.9), top=Inches(1.15), width=Inches(1.1)):
    bar = slide.shapes.add_shape(1, left, top, width, Pt(6))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def add_text(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    return tf


def style(para, text, size, color, bold=False, align=PP_ALIGN.LEFT,
          font=FONT, space_after=Pt(10)):
    para.alignment = align
    para.space_after = space_after
    run = para.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


# =========================================================
# 1. Title
# =========================================================
s = add_slide()
tf = add_text(s, Inches(1.2), Inches(2.6), Inches(11), Inches(2.4))
style(tf.paragraphs[0], "Marrow", 88, TEXT, bold=True, align=PP_ALIGN.CENTER,
      space_after=Pt(18))
style(tf.add_paragraph(), "Know what your tests actually cover.", 32, ACCENT,
      align=PP_ALIGN.CENTER)
bar = accent_bar(s, left=Inches(6.06), top=Inches(4.7), width=Inches(1.2))

# =========================================================
# 2. Call to action  (moved to slide 2 per instruction)
# =========================================================
s = add_slide()
accent_bar(s)
tf = add_text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(4.5))
style(tf.paragraphs[0], "Install Marrow", 52, TEXT, bold=True, space_after=Pt(28))
style(tf.add_paragraph(), "pipx install marrow", 40, ACCENT, bold=True,
      font="Menlo", space_after=Pt(28))
style(tf.add_paragraph(), "Works with pytest, Jest, and go test.", 26, MUTED)

# =========================================================
# 3. The problem
# =========================================================
s = add_slide()
accent_bar(s)
tf = add_text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(4.5))
style(tf.paragraphs[0], "Big test suites hide their gaps.", 46, TEXT, bold=True,
      space_after=Pt(30))
for line in [
    "Large suites are slow, and nobody knows which tests cover which code.",
    "Dead tests linger, quietly wasting every run.",
    "Real coverage gaps go unnoticed until something breaks.",
]:
    style(tf.add_paragraph(), line, 26, TEXT, space_after=Pt(16))

# =========================================================
# 4. The idea
# =========================================================
s = add_slide()
accent_bar(s)
tf = add_text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(4.5))
style(tf.paragraphs[0], "Watch one run. Draw the real map.", 46, TEXT,
      bold=True, space_after=Pt(30))
style(tf.add_paragraph(),
      "Marrow instruments a single test run and produces a test → code "
      "coverage map.", 28, TEXT, space_after=Pt(18))
style(tf.add_paragraph(), "No annotations. No config.", 28, ACCENT, bold=True)

# =========================================================
# 5. Why now  (new slide inserted per learned preference)
# =========================================================
s = add_slide()
accent_bar(s)
tf = add_text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(4.5))
style(tf.paragraphs[0], "Why now", 46, TEXT, bold=True, space_after=Pt(30))
style(tf.add_paragraph(),
      "Test suites have grown into the thousands — too large to hold in "
      "anyone's head.", 28, TEXT, space_after=Pt(18))
style(tf.add_paragraph(),
      "Manual coverage tracking has become untenable; spreadsheets and "
      "guesswork no longer scale.", 28, TEXT, space_after=Pt(18))
style(tf.add_paragraph(),
      "The map has to be generated automatically — that's the only way "
      "it stays true.", 28, ACCENT, bold=True)

# =========================================================
# 6. How it works
# =========================================================
s = add_slide()
accent_bar(s)
tf = add_text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(5.0))
style(tf.paragraphs[0], "How it works", 46, TEXT, bold=True, space_after=Pt(30))
steps = [
    ("1", "Run", "marrow watch -- <your test cmd>"),
    ("2", "Record", "Marrow captures which lines each test exercised."),
    ("3", "Map", "It emits an interactive map plus dead tests and untested lines."),
]
for num, head, body in steps:
    p = tf.add_paragraph()
    p.space_after = Pt(18)
    r = p.add_run()
    r.text = f"{num}  "
    r.font.name = FONT
    r.font.size = Pt(26)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    r2 = p.add_run()
    r2.text = f"{head} — "
    r2.font.name = FONT
    r2.font.size = Pt(26)
    r2.font.bold = True
    r2.font.color.rgb = TEXT
    r3 = p.add_run()
    r3.text = body
    r3.font.name = "Menlo" if num == "1" else FONT
    r3.font.size = Pt(24)
    r3.font.color.rgb = MUTED if num == "1" else TEXT

prs.save("deck.pptx")
print("Saved deck.pptx with", len(prs.slides._sldIdLst), "slides.")
