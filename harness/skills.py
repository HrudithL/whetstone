"""Per-skill descriptors for the showcase harness (M4b).

M3's harness hard-coded great-tables everywhere: the runner mounted one skill dir, the stub emitted
``gt.GT(df)`` code, the agent prompt said "write ``table.py`` ... ``gtsave``", and ``honors()``
always parsed Python. M4b generalizes that so **one runner serves many skills**. Everything that is
skill-specific now lives in a :class:`SkillSpec`; great-tables is simply the first entry.

A scenario's ``skill:`` field selects its :class:`SkillSpec` (and the vendored skill directory under
``harness/skill/<name>/`` that the ``--agent`` generator mounts). The spec carries:

* ``output`` — the primary artifact the generator writes and that ``honors()`` / the cold→warm diff
  read (the old hard-coded ``table.py``). For great-tables this is Python; for a web-design skill it
  is an ``index.html``; for a slide skill it is a python-pptx script.
* ``check_language`` — how ``honors()`` normalizes the primary output before matching a check's
  pattern. ``python`` reuses the AST/tokenize comment+docstring stripper; ``html`` strips
  ``<!-- -->`` and ``/* */``, so an agent's *explanatory* comment can't fool a ``*_absent`` check.
* ``required_artifacts`` — extra files a live ``--agent`` run MUST produce (fail loud if missing),
  e.g. great-tables' rendered ``table.png`` and native ``table.html``. The free stub does not
  produce these (it only fabricates the checkable primary output).
* ``intent_lead`` / ``intent_dimensions`` — the recall ``intent`` names the *space* a styling
  decision spans (retrieval must match the seeded scopes, not be handed them). ``intent_lead`` is
  the noun phrase ("a great-tables display table"); ``intent_dimensions`` the comma list.
* ``prompt_tail`` — the skill-specific generation instructions appended to the scenario prompt.
  ``{data}`` is substituted with the input file's basename.

The stub's per-language *carrier* (how it embeds a check token in the fabricated output) lives in
``generate.py`` keyed by ``check_language``, so this module stays pure data.
"""

from __future__ import annotations

from dataclasses import dataclass

# How honors() normalizes the primary output before matching. Extend deliberately: a new language
# needs a stripper in generate.code_for_check AND a stub carrier in generate._stub_carrier.
CHECK_LANGUAGES = ("python", "html")


@dataclass(frozen=True)
class SkillSpec:
    """Everything skill-specific the generalized runner/generator needs for one skill."""

    name: str  # vendored dir under harness/skill/, and the Agent-SDK mount name
    output: str  # primary artifact filename (honors()/diff read this)
    check_language: str  # "python" | "html"
    intent_lead: str  # recall-intent noun phrase, e.g. "a great-tables display table"
    intent_dimensions: str  # comma list of styling dimensions the intent elaborates
    prompt_tail: str  # generation instructions appended to the prompt; "{data}" -> input basename
    required_artifacts: tuple[str, ...] = ()  # files a live --agent run MUST also produce


_GREAT_TABLES = SkillSpec(
    name="great-tables",
    output="table.py",
    check_language="python",
    required_artifacts=("table.png", "table.html"),
    intent_lead="a great-tables display table",
    intent_dimensions=(
        "column alignment, number formatting, currency formatting, percentage formatting, "
        "color palette and encoding, column-label and header styling, row-group label styling, "
        "column grouping and spanners, row ordering, and table density"
    ),
    prompt_tail=(
        "The data is in `{data}` in the current directory. Write a Python script "
        "`table.py` that builds the requested table with `great_tables`, then render it to "
        "`table.png` with Great Tables' gtsave (the skill's mandatory renderer, "
        '`table.gtsave("table.png")`). Also write the table\'s self-contained HTML to '
        "`table.html` via `<your GT object>.as_raw_html()` so it can be embedded natively. "
        "Run the script to confirm it works."
    ),
)


_FRONTEND_DESIGN = SkillSpec(
    name="frontend-design",
    output="index.html",
    check_language="html",
    # No extra render step: index.html IS the artifact (self-contained, opens in a browser). The
    # AgentGenerator already fail-loud-checks the primary output is non-empty / non-whitespace.
    required_artifacts=(),
    intent_lead="a frontend web design",
    intent_dimensions=(
        "color palette and accent, typography and type scale, letter-spacing and casing, "
        "corner radius, spacing and layout, shadow and depth, and motion"
    ),
    prompt_tail=(
        "The brief is in `{data}` in the current directory. Build a single self-contained "
        "`index.html` — all CSS in one inline `<style>` block, no external assets, no CDN, no "
        "build step — that implements the brief. Use the frontend-design skill's guidance. Write "
        "only `index.html`; do not create any other files."
    ),
)


_PPTX = SkillSpec(
    name="pptx",
    output="deck.py",
    check_language="python",  # a python-pptx script → reuse the AST/tokenize stripper
    required_artifacts=("deck.pptx",),  # the script must actually run and save the deck
    intent_lead="a slide deck",
    intent_dimensions=(
        "slide layout, title alignment, typography, color and accent, background, "
        "bullet density, and aspect ratio"
    ),
    prompt_tail=(
        "The outline is in `{data}` in the current directory. Write `deck.py` using `python-pptx` "
        "that builds the deck and saves it to `deck.pptx`, then run the script to produce "
        "`deck.pptx`. Write only `deck.py`; do not create any other files."
    ),
)


# Registry. Additional skills are registered in their own slices as they are vendored under
# harness/skill/. Keyed by the scenario's `skill:` field.
SPECS: dict[str, SkillSpec] = {s.name: s for s in (_GREAT_TABLES, _FRONTEND_DESIGN, _PPTX)}


def get_spec(skill: str) -> SkillSpec:
    """Return the :class:`SkillSpec` for ``skill``. Raises ``KeyError`` naming the known skills."""
    try:
        return SPECS[skill]
    except KeyError:
        known = ", ".join(sorted(SPECS)) or "(none)"
        raise KeyError(f"unknown skill {skill!r}; vendored skills: {known}") from None
