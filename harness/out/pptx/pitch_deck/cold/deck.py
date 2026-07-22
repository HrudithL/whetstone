from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

# Create presentation
prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(7.5)

# Define color palette
BG_COLOR = RGBColor(255, 255, 255)  # White
TEXT_COLOR = RGBColor(40, 40, 40)  # Dark gray
ACCENT_COLOR = RGBColor(0, 120, 150)  # Teal
SUBTITLE_COLOR = RGBColor(100, 100, 100)  # Medium gray

# Slide 1: Title Slide
slide1 = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
background = slide1.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = BG_COLOR

# Add title
title_box = slide1.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(9), Inches(1.5))
title_frame = title_box.text_frame
title_frame.text = "Marrow"
title_para = title_frame.paragraphs[0]
title_para.alignment = PP_ALIGN.CENTER
title_para.font.name = "Calibri"
title_para.font.size = Pt(88)
title_para.font.color.rgb = ACCENT_COLOR
title_para.font.bold = True

# Add subtitle
subtitle_box = slide1.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(9), Inches(1.5))
subtitle_frame = subtitle_box.text_frame
subtitle_frame.word_wrap = True
subtitle_frame.text = "Know what your tests actually cover."
subtitle_para = subtitle_frame.paragraphs[0]
subtitle_para.alignment = PP_ALIGN.CENTER
subtitle_para.font.name = "Calibri"
subtitle_para.font.size = Pt(32)
subtitle_para.font.color.rgb = SUBTITLE_COLOR

# Slide 2: The Problem
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
background = slide2.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = BG_COLOR

# Title
title_box2 = slide2.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(9), Inches(1))
title_frame2 = title_box2.text_frame
title_frame2.text = "Big test suites hide their gaps."
title_para2 = title_frame2.paragraphs[0]
title_para2.font.name = "Calibri"
title_para2.font.size = Pt(54)
title_para2.font.color.rgb = TEXT_COLOR
title_para2.font.bold = True

# Body
body_box2 = slide2.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(4.5))
body_frame2 = body_box2.text_frame
body_frame2.word_wrap = True
body_text2 = """Large test suites are slow and hard to navigate.

Nobody knows which tests cover which code.

Dead tests linger. Real gaps go unnoticed."""
body_frame2.text = body_text2
for para in body_frame2.paragraphs:
    para.font.name = "Calibri"
    para.font.size = Pt(28)
    para.font.color.rgb = TEXT_COLOR
    para.space_before = Pt(12)
    para.space_after = Pt(12)

# Slide 3: The Idea
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
background = slide3.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = BG_COLOR

# Title
title_box3 = slide3.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(9), Inches(1))
title_frame3 = title_box3.text_frame
title_frame3.text = "Watch one run. Draw the real map."
title_para3 = title_frame3.paragraphs[0]
title_para3.font.name = "Calibri"
title_para3.font.size = Pt(54)
title_para3.font.color.rgb = TEXT_COLOR
title_para3.font.bold = True

# Body
body_box3 = slide3.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(4.5))
body_frame3 = body_box3.text_frame
body_frame3.word_wrap = True
body_text3 = """Marrow instruments a single test run.

Produces a test → code coverage map.

No annotations. No config."""
body_frame3.text = body_text3
for para in body_frame3.paragraphs:
    para.font.name = "Calibri"
    para.font.size = Pt(28)
    para.font.color.rgb = TEXT_COLOR
    para.space_before = Pt(12)
    para.space_after = Pt(12)

# Slide 4: How It Works
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
background = slide4.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = BG_COLOR

# Title
title_box4 = slide4.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(9), Inches(0.8))
title_frame4 = title_box4.text_frame
title_frame4.text = "How it works"
title_para4 = title_frame4.paragraphs[0]
title_para4.font.name = "Calibri"
title_para4.font.size = Pt(54)
title_para4.font.color.rgb = TEXT_COLOR
title_para4.font.bold = True

# Body with three steps
body_box4 = slide4.shapes.add_textbox(Inches(1), Inches(1.6), Inches(8), Inches(5))
body_frame4 = body_box4.text_frame
body_frame4.word_wrap = True
body_text4 = """1. Run: marrow watch -- <your test cmd>

2. Marrow records which lines each test exercised

3. Emits an interactive map, lists dead tests
   and untested lines"""
body_frame4.text = body_text4
for para in body_frame4.paragraphs:
    para.font.name = "Calibri"
    para.font.size = Pt(24)
    para.font.color.rgb = TEXT_COLOR
    para.space_before = Pt(10)
    para.space_after = Pt(10)

# Slide 5: Call to Action
slide5 = prs.slides.add_slide(prs.slide_layouts[6])
background = slide5.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = BG_COLOR

# Title
title_box5 = slide5.shapes.add_textbox(Inches(0.5), Inches(1), Inches(9), Inches(1.2))
title_frame5 = title_box5.text_frame
title_frame5.text = "Install Marrow"
title_para5 = title_frame5.paragraphs[0]
title_para5.alignment = PP_ALIGN.CENTER
title_para5.font.name = "Calibri"
title_para5.font.size = Pt(54)
title_para5.font.color.rgb = TEXT_COLOR
title_para5.font.bold = True

# Command
cmd_box = slide5.shapes.add_textbox(Inches(1), Inches(2.8), Inches(8), Inches(1.2))
cmd_frame = cmd_box.text_frame
cmd_frame.text = "pipx install marrow"
cmd_para = cmd_frame.paragraphs[0]
cmd_para.alignment = PP_ALIGN.CENTER
cmd_para.font.name = "Courier New"
cmd_para.font.size = Pt(36)
cmd_para.font.color.rgb = ACCENT_COLOR
cmd_para.font.bold = True

# Supported frameworks
support_box = slide5.shapes.add_textbox(Inches(1), Inches(4.5), Inches(8), Inches(2))
support_frame = support_box.text_frame
support_frame.word_wrap = True
support_frame.text = "Works with pytest, Jest, go test."
support_para = support_frame.paragraphs[0]
support_para.alignment = PP_ALIGN.CENTER
support_para.font.name = "Calibri"
support_para.font.size = Pt(28)
support_para.font.color.rgb = SUBTITLE_COLOR

# Save presentation
prs.save("deck.pptx")
print("✓ Deck created: deck.pptx")
