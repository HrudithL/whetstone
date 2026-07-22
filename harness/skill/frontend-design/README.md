# Vendored frontend-design skill

A trimmed adaptation of Anthropic's official **frontend-design** skill
([`anthropics/claude-code`](https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design/skills/frontend-design)),
vendored so the showcase harness is self-contained. Mounted by the runner's `--agent` (live)
generator for `skill: frontend-design` scenarios.

## Adaptation from source

The upstream skill is a multi-file plugin. This copy condenses its guidance into a single `SKILL.md`
(design principles + the plan→build→critique process) and adds a **Rule 0** making the user's /
learned-layer instructions override every stylistic default — the hook the showcase relies on: the
COLD run designs distinctively but does not happen to honor the scenario's arbitrary preference,
while the WARM run applies the recalled preference exactly on top. The heavy reference material and
`LICENSE.txt` were not copied; see the upstream repo for the full, canonical skill.

The runner asks the model to write a **single self-contained `index.html`** (inline `<style>`, no
build step or CDN) — see this skill's `SkillSpec` in [`../../skills.py`](../../skills.py). Preferences
are checked against the HTML/CSS text (`check_language: html`).
