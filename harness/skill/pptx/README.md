# Vendored pptx skill

A compact skill in the flavor of Anthropic's **pptx** document skill
([`anthropics/skills`](https://github.com/anthropics/skills)), vendored so the showcase harness is
self-contained. Mounted by the runner's `--agent` (live) generator for `skill: pptx` scenarios.

## Adaptation from source

Anthropic's upstream pptx skill is a large, multi-file document skill (create/edit `.pptx` via
`python-pptx` plus helper scripts, oriented at faithful document round-tripping). This copy keeps
just the **build-a-deck-with-python-pptx** workflow the showcase needs, and adds a **Rule 0** making
the learned layer override stylistic defaults — the hook the showcase relies on: the COLD run builds
a sensible deck that does not happen to honor the scenario's arbitrary preference, while the WARM run
applies the recalled preference (a specific font, title alignment, ...) on every slide. The upstream
helper library and reference material were not copied; see the upstream repo for the full skill.

The runner asks the model to write **`deck.py`** and run it to produce **`deck.pptx`** — see this
skill's `SkillSpec` in [`../../skills.py`](../../skills.py). Because the output is a python-pptx
script, preferences are checked against the **Python** source (`check_language: python`, reusing the
AST/tokenize stripper). `python-pptx` must be importable in the run venv (it is in the `[showcase]`
extra).
