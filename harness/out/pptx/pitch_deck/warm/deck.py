#!/usr/bin/env python3
"""
Marrow pitch deck generator using python-pptx.
Creates a 5-slide presentation with consistent design and formatting.
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

# Create presentation
prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(7.5)

# Define colors
DARK_BLUE = RGBColor(25, 55, 95)
LIGHT_GRAY = RGBColor(240, 240, 245)
WHITE = RGBColor(255, 255, 255)
ACCENT_BLUE = RGBColor(66, 135, 245)

def apply_consolas_to_run(run, font_size=14, bold=False, color=DARK_BLUE):
    """Apply Consolas font and formatting to a text run."""
    run.font.name = "Consolas"
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color


def create_slide_with_title_and_content(prs, title_text, content_text=None, subtitle=None):
    """Helper function to create a standard slide layout."""
    blank_slide_layout = prs.slide_layouts[6]  # Blank layout
    slide = prs.slides.add_slide(blank_slide_layout)

    # Add background
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = WHITE

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(9), Inches(1))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    title_p = title_frame.paragraphs[0]
    title_p.text = title_text
    title_p.alignment = PP_ALIGN.RIGHT
    apply_consolas_to_run(title_p.runs[0], font_size=44, bold=True, color=DARK_BLUE)

    # Add subtitle if provided
    if subtitle:
        subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.6), Inches(9), Inches(1))
        subtitle_frame = subtitle_box.text_frame
        subtitle_frame.word_wrap = True
        subtitle_p = subtitle_frame.paragraphs[0]
        subtitle_p.text = subtitle
        subtitle_p.alignment = PP_ALIGN.RIGHT
        apply_consolas_to_run(subtitle_p.runs[0], font_size=24, color=ACCENT_BLUE)

        content_y = 3.0
    else:
        content_y = 2.0

    # Add content if provided
    if content_text:
        content_box = slide.shapes.add_textbox(Inches(0.8), Inches(content_y), Inches(8.4), Inches(4.5))
        content_frame = content_box.text_frame
        content_frame.word_wrap = True

        # Handle content as list of bullet points or paragraphs
        if isinstance(content_text, list):
            for i, text in enumerate(content_text):
                if i == 0:
                    p = content_frame.paragraphs[0]
                else:
                    p = content_frame.add_paragraph()
                p.text = text
                p.level = 0
                for run in p.runs:
                    apply_consolas_to_run(run, font_size=18, color=DARK_BLUE)
        else:
            p = content_frame.paragraphs[0]
            p.text = content_text
            for run in p.runs:
                apply_consolas_to_run(run, font_size=18, color=DARK_BLUE)

    return slide


# Slide 1: Title Slide
slide1 = create_slide_with_title_and_content(
    prs,
    title_text="Marrow",
    subtitle="Know what your tests actually cover."
)

# Slide 2: The Problem
slide2 = create_slide_with_title_and_content(
    prs,
    title_text="The Problem",
    content_text=[
        "• Big test suites hide their gaps",
        "",
        "• Large suites are slow and nobody knows",
        "  which tests cover which code",
        "",
        "• Dead tests linger and real gaps",
        "  go unnoticed"
    ]
)

# Slide 3: The Idea
slide3 = create_slide_with_title_and_content(
    prs,
    title_text="The Idea",
    content_text=[
        "Watch one run. Draw the real map.",
        "",
        "• Marrow instruments a single test run",
        "",
        "• Produces a test→code coverage map",
        "",
        "• No annotations, no config needed"
    ]
)

# Slide 4: How It Works
slide4 = create_slide_with_title_and_content(
    prs,
    title_text="How It Works",
    content_text=[
        "1. Run: marrow watch -- <your test cmd>",
        "",
        "2. Marrow records which lines each test",
        "   exercised",
        "",
        "3. Emits interactive map + dead tests +",
        "   untested lines"
    ]
)

# Slide 5: Call to Action
blank_slide_layout = prs.slide_layouts[6]
slide5 = prs.slides.add_slide(blank_slide_layout)
background = slide5.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = DARK_BLUE

# Title on CTA slide
cta_title = slide5.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(9), Inches(1))
cta_title_frame = cta_title.text_frame
cta_title_p = cta_title_frame.paragraphs[0]
cta_title_p.text = "Install Marrow"
cta_title_p.alignment = PP_ALIGN.CENTER
apply_consolas_to_run(cta_title_p.runs[0], font_size=48, bold=True, color=WHITE)

# Command
cta_cmd = slide5.shapes.add_textbox(Inches(0.5), Inches(3.0), Inches(9), Inches(1))
cta_cmd_frame = cta_cmd.text_frame
cta_cmd_p = cta_cmd_frame.paragraphs[0]
cta_cmd_p.text = "pipx install marrow"
cta_cmd_p.alignment = PP_ALIGN.CENTER
apply_consolas_to_run(cta_cmd_p.runs[0], font_size=32, color=ACCENT_BLUE)

# Compatibility
cta_compat = slide5.shapes.add_textbox(Inches(0.5), Inches(4.5), Inches(9), Inches(1.5))
cta_compat_frame = cta_compat.text_frame
cta_compat_p = cta_compat_frame.paragraphs[0]
cta_compat_p.text = "Works with pytest, Jest, go test."
cta_compat_p.alignment = PP_ALIGN.CENTER
apply_consolas_to_run(cta_compat_p.runs[0], font_size=24, color=WHITE)

# Save presentation
prs.save('deck.pptx')
print("✓ deck.pptx created successfully!")
