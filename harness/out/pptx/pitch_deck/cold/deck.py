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
TEXT_COLOR = RGBColor(30, 30, 30)   # Dark gray/black
ACCENT_COLOR = RGBColor(0, 150, 136)  # Teal accent

def set_slide_background(slide, color):
    """Set slide background color"""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_title_slide(prs, title, subtitle):
    """Create a title slide"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    set_slide_background(slide, BG_COLOR)

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(9), Inches(1.5))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    title_p = title_frame.paragraphs[0]
    title_p.text = title
    title_p.font.size = Pt(72)
    title_p.font.bold = True
    title_p.font.color.rgb = ACCENT_COLOR
    title_p.alignment = PP_ALIGN.CENTER
    title_p.font.name = "Calibri"

    # Add subtitle
    subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(9), Inches(1))
    subtitle_frame = subtitle_box.text_frame
    subtitle_frame.word_wrap = True
    subtitle_p = subtitle_frame.paragraphs[0]
    subtitle_p.text = subtitle
    subtitle_p.font.size = Pt(32)
    subtitle_p.font.color.rgb = TEXT_COLOR
    subtitle_p.alignment = PP_ALIGN.CENTER
    subtitle_p.font.name = "Calibri"

def add_content_slide(prs, title, content_lines):
    """Create a content slide with title and bullet points"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    set_slide_background(slide, BG_COLOR)

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.75), Inches(0.5), Inches(8.5), Inches(1))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    title_p = title_frame.paragraphs[0]
    title_p.text = title
    title_p.font.size = Pt(54)
    title_p.font.bold = True
    title_p.font.color.rgb = ACCENT_COLOR
    title_p.font.name = "Calibri"

    # Add content
    content_box = slide.shapes.add_textbox(Inches(1.5), Inches(1.8), Inches(8), Inches(5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True

    for i, line in enumerate(content_lines):
        if i == 0:
            p = text_frame.paragraphs[0]
        else:
            p = text_frame.add_paragraph()

        p.text = line
        p.font.size = Pt(28)
        p.font.color.rgb = TEXT_COLOR
        p.font.name = "Calibri"
        p.space_before = Pt(12)
        p.space_after = Pt(12)
        p.level = 0

# Slide 1: Title
add_title_slide(prs, "Marrow", "Know what your tests actually cover.")

# Slide 2: The Problem
add_content_slide(prs, "Big test suites hide their gaps.", [
    "Large suites are slow and opaque",
    "Nobody knows which tests cover which code",
    "Dead tests linger, real gaps go unnoticed"
])

# Slide 3: The Idea
add_content_slide(prs, "Watch one run. Draw the real map.", [
    "Instruments a single test run",
    "Produces a test→code coverage map",
    "No annotations, no config"
])

# Slide 4: How it Works
add_content_slide(prs, "How it works", [
    "Run: marrow watch -- <your test cmd>",
    "Records which lines each test exercised",
    "Emits interactive map + dead tests + untested lines"
])

# Slide 5: Call to Action
add_content_slide(prs, "Install Marrow", [
    "pipx install marrow",
    "Works with pytest, Jest, go test"
])

# Save the presentation
prs.save("deck.pptx")
print("Deck saved to deck.pptx")
