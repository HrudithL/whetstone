# Whetstone showcase harness (M3)

**Internal, command-only tooling.** This is *not* part of the distributed `whetstone` package, is
never imported by the MCP server, and **never runs in CI**. Its one job is to generate the
before/after artifacts and metrics that the Quarto site in [`../docs/`](../docs/) reads from
[`out/`](out/).

## What it proves

One claim: *a correction the skill received once is tracked and keeps being honored on later runs.*
It shows this two ways:

1. **See it** — a before / learned-layer / after triptych. The middle panel is the **verbatim
   `recall()` payload** the model received (ids, scopes, weights, issue/preference text).
2. **Measure it** — two honest metrics read straight from the store's `events.jsonl` (never
   hand-set):
   - **runs-to-stick** — how many task runs / correction cycles occur before a preference is
     captured and then applied without needing re-correction.
   - **reinforcement / value-over-time** — the learning's `weight`/`recurrence` trajectory across
     later runs (does it survive decay, keep getting reinforced, stay applied).

There is **no LLM judge** — the harness measures how the learned layer is *tracked*, not whether one
table is subjectively prettier than another.

## How it works

Each scenario pairs a task for one **skill** (`skill:` — great-tables, frontend-design, pptx, ...)
with one or more arbitrary subjective preferences (see [`schema.py`](schema.py) and
[`skills.py`](skills.py)). Per scenario the runner:

1. **COLD** — generates the skill's output with an **empty** Whetstone store (the preference is
   typically not honored).
2. **Seed** — replays the scenario's scripted feedback through Whetstone's `capture`/`revise` tools,
   turning the preference into a tracked learning/issue (committed to the store, logged to
   `events.jsonl`).
3. **WARM** — regenerates with the `recall()` payload injected, and iterates to measure
   runs-to-stick; reads the weight trajectory for value-over-time.

Generation drives a live model via the Claude Agent SDK with the scenario's skill mounted (adapted
from `gtskill`'s SDK path); each skill's primary artifact, generation prompt, and check language come
from its `SkillSpec` in [`skills.py`](skills.py) (great-tables → `table.py`/`table.png`,
frontend-design → `index.html`, pptx → `deck.py`/`deck.pptx`). A run needs `ANTHROPIC_API_KEY` —
which is exactly why it is command-only and its outputs are committed.

## Environment (pinned)

[`config.py`](config.py) pins the harness environment so runs are reproducible regardless of the
maintainer's shell:

- **backend:** `sentence-transformers` / `all-MiniLM-L6-v2` (thresholds are calibrated for ST; the
  light `hashing` default is not used here).
- **store root:** an isolated, gitignored `harness/.store/` (never touches a real user store).
- **supervision:** `autonomous` (seeding runs unattended, no confirmation prompts).

## Run it

```bash
# from the repo root
pip install -e ".[showcase,embeddings]"
export ANTHROPIC_API_KEY=sk-ant-...          # or put it in harness/.env (gitignored)

python -m harness.run --agent                 # real (paid): regenerates the committed out/ artifacts
python -m harness.run --stub                  # free deterministic pipeline check (does NOT commit real artifacts)
python -m harness.run --agent --scenario sp500_monthly_performance   # one scenario
```

A mode (`--agent` or `--stub`) is **required** — a bare `python -m harness.run` refuses to run, since
each run clears `out/<skill>/<scenario>/` first and an accidental stub run would overwrite the real
artifacts. (`--stub` routes its output + store to throwaway temp dirs, so it never touches `out/`.)

**Prerequisites for a real run** (beyond the pip extras):

- The **Claude Code CLI** on `PATH` (`claude-agent-sdk` drives it) — `npm i -g @anthropic-ai/claude-code`.
- A **headless Chrome/Chromium** binary *only if* you export `table.png` snapshots: great-tables'
  PNG export renders through headless Chrome. The site itself renders great-tables **natively as
  HTML** in Quarto (the whole point — real tables, not screenshots), so the `table.png` artifacts in
  `out/` are an optional convenience; set `CHROME_PATH` if a run cannot find a browser.

## Layout

```
harness/
  config.py         pinned showcase environment (ST backend, isolated store, autonomous)
  schema.py         scenario dataclasses + validating loader; the harness<->site contract
  skills.py         per-skill SkillSpec registry (primary artifact, check language, prompt)
  skill/<name>/     one vendored Claude skill per dir, mounted by the --agent runner
  scenarios/        one *.yaml per scenario (each names its `skill:`)
  data/             input files scenarios reference (CSVs, design briefs)
  generate.py       stub + live Agent-SDK generators (both skill-driven)
  out/<skill>/<scenario>/   generated, committed artifacts the site reads
  run.py            cold/seed/warm runner
  metrics.py        aggregates out/**/summary.json -> out/metrics.json (per-skill + overall)
```
