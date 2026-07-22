from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

# Create presentation with 1:1 square format (10" x 10")
prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(10)

# Define colors
DARK_BG = RGBColor(20, 20, 30)
ACCENT_BLUE = RGBColor(66, 135, 245)
TEXT_WHITE = RGBColor(255, 255, 255)
TEXT_LIGHT_GRAY = RGBColor(220, 220, 220)

def add_slide_with_bg():
    """Create a blank slide with dark background."""
    blank_layout = prs.slide_layouts[6]  # Blank layout
    slide = prs.slides.add_slide(blank_layout)

    # Add dark background
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = DARK_BG

    return slide

def set_text_font(text_frame, font_name="Consolas", size=Pt(24), color=TEXT_WHITE):
    """Set font properties for all runs in a text frame."""
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.name = font_name
            run.font.size = size
            run.font.color.rgb = color

def add_title_subtitle_slide(title_text, subtitle_text):
    """Add a slide with title and subtitle."""
    slide = add_slide_with_bg()

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(3.5), Inches(9), Inches(1.5))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    p = title_frame.paragraphs[0]
    p.text = title_text
    p.alignment = PP_ALIGN.CENTER
    p.font.name = "Consolas"
    p.font.size = Pt(54)
    p.font.bold = True
    p.font.color.rgb = ACCENT_BLUE

    # Add subtitle
    subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(5.2), Inches(9), Inches(2))
    subtitle_frame = subtitle_box.text_frame
    subtitle_frame.word_wrap = True
    p = subtitle_frame.paragraphs[0]
    p.text = subtitle_text
    p.alignment = PP_ALIGN.CENTER
    p.font.name = "Consolas"
    p.font.size = Pt(28)
    p.font.color.rgb = TEXT_LIGHT_GRAY

    return slide

def add_content_slide(title_text, body_text):
    """Add a slide with title and body text."""
    slide = add_slide_with_bg()

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.8), Inches(9), Inches(1))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    p = title_frame.paragraphs[0]
    p.text = title_text
    p.font.name = "Consolas"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = ACCENT_BLUE

    # Add accent line
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(2), Inches(2), Inches(0))
    line.line.color.rgb = ACCENT_BLUE
    line.line.width = Pt(2)

    # Add body text
    body_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.5), Inches(8.4), Inches(6.5))
    body_frame = body_box.text_frame
    body_frame.word_wrap = True

    for line_text in body_text:
        if body_frame.text:
            p = body_frame.add_paragraph()
        else:
            p = body_frame.paragraphs[0]

        p.text = line_text
        p.font.name = "Consolas"
        p.font.size = Pt(20)
        p.font.color.rgb = TEXT_LIGHT_GRAY
        p.space_before = Pt(6)
        p.space_after = Pt(6)

    return slide

# Slide 1: Title
add_title_subtitle_slide("Marrow", "Know what your tests actually cover.")

# Slide 2: The Problem
problem_text = [
    "Big test suites hide their gaps.",
    "",
    "Large suites are slow and nobody knows which tests cover which code, so dead tests linger and real gaps go unnoticed."
]
add_content_slide("The Problem", problem_text)

# Slide 3: The Idea
idea_text = [
    "Watch one run. Draw the real map.",
    "",
    "Marrow instruments a single test run and produces a test→code coverage map — no annotations, no config."
]
add_content_slide("The Idea", idea_text)

# Slide 4: How It Works
howto_text = [
    "1. Run: marrow watch -- <your test cmd>",
    "",
    "2. Marrow records which lines each test exercised",
    "",
    "3. Emits interactive map + list of dead tests and untested lines"
]
add_content_slide("How It Works", howto_text)

# Slide 5: Call to Action
slide = add_slide_with_bg()

# Add main heading
cta_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(9), Inches(1.5))
cta_frame = cta_box.text_frame
cta_frame.word_wrap = True
p = cta_frame.paragraphs[0]
p.text = "Install Marrow"
p.alignment = PP_ALIGN.CENTER
p.font.name = "Consolas"
p.font.size = Pt(48)
p.font.bold = True
p.font.color.rgb = ACCENT_BLUE

# Add install command
cmd_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(9), Inches(1))
cmd_frame = cmd_box.text_frame
cmd_frame.word_wrap = True
p = cmd_frame.paragraphs[0]
p.text = "pipx install marrow"
p.alignment = PP_ALIGN.CENTER
p.font.name = "Consolas"
p.font.size = Pt(32)
p.font.color.rgb = ACCENT_BLUE

# Add supported frameworks
support_box = slide.shapes.add_textbox(Inches(0.5), Inches(5.8), Inches(9), Inches(2))
support_frame = support_box.text_frame
support_frame.word_wrap = True
p = support_frame.paragraphs[0]
p.text = "Works with pytest, Jest, go test."
p.alignment = PP_ALIGN.CENTER
p.font.name = "Consolas"
p.font.size = Pt(24)
p.font.color.rgb = TEXT_LIGHT_GRAY

# Save the presentation
prs.save('deck.pptx')
print("✓ deck.pptx created successfully")
