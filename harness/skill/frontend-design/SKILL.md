---
name: frontend-design
description: Use when building or restyling any web UI — landing pages, hero sections, pricing cards, dashboards, marketing pages — as self-contained HTML/CSS. Drives distinctive, intentional visual design (typography, color, layout, motion) grounded in the brief's own subject, so the result reads as a deliberate identity rather than a templated default. Invoke before writing any HTML: the design plan shapes the whole page.
---

# Frontend Design

Build UI that reads as a **deliberate visual identity**, not a templated default. Every choice —
type, color, spacing, motion — should be traceable to *this* brief's subject and audience.

## Ground it in the subject

Establish the concrete subject, its audience, and the page's primary purpose before designing. The
subject's own world — its materials, vocabulary, and artifacts — is where distinctive choices come
from. Build with the brief's actual content throughout; do not fill with lorem ipsum.

## Design principles

- **Hero as thesis.** Open with the most characteristic element in the subject's world (headline,
  image, demo, interactive moment). Avoid generic openings unless genuinely optimal.
- **Typography as personality.** Choose display and body typefaces deliberately for this project.
  Establish a clear type scale with intentional weights, widths, and letter-spacing that is
  memorable rather than neutral.
- **Structure encodes meaning.** Use numbering, dividers, and labels only when they convey real
  information — never as decoration.
- **Deliberate motion.** Add animation only where it serves the subject; gratuitous motion reads as
  AI-generated. Respect `prefers-reduced-motion`.
- **Match complexity to vision.** Maximalist work needs elaborate execution; minimal work demands
  precision in spacing, type, and detail.
- **Color with intent.** Commit to a small named palette (4–6 hex values) and one signature accent;
  do not scatter unrelated hues.

## Process: plan, then build, then critique

1. **Plan** a design: named palette (hex), typefaces (display / body / utility), layout concept, and
   the one signature element where boldness is concentrated.
2. **Build** a single self-contained page — inline `<style>`, no build step, no external CDN or
   assets. Responsive, with visible focus states and reduced-motion support.
3. **Critique** against the brief: revise anything that resembles a generic default rather than a
   choice specific to *this* brief. Keep surrounding details quiet and disciplined.

Avoid the tell-tale AI-generated defaults (warm cream + serif display; near-black + acid-green;
broadsheet layouts with hairline rules) *unless* the brief genuinely calls for one.

## Rule 0 — the user's instructions override every default

Every guideline here is a **default**. Any explicit instruction in the prompt or the learned layer
(a specific accent hex, font, corner radius, letter-spacing, casing) **wins** — apply it exactly and
drop the conflicting default silently. The guidelines decide what to do only *in the absence of* an
instruction; they never override one.
