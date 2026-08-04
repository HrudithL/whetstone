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
- **R with `ggplot2`/`tidyverse` on `PATH`** for `skill: ggplot2` scenarios — R isn't pip-installable,
  so unlike the Python skills there's no venv-pinned dependency; install it however you normally would
  (e.g. `brew install r` + `Rscript -e 'install.packages("tidyverse")'`).
- A **headless Chrome/Chromium** binary *only if* you export `table.png` snapshots: great-tables'
  PNG export renders through headless Chrome. The site itself renders great-tables **natively as
  HTML** in Quarto (the whole point — real tables, not screenshots), so the `table.png` artifacts in
  `out/` are an optional convenience; set `CHROME_PATH` if a run cannot find a browser.

## Calibration KPIs (M5b)

The scenario pass above measures *runs-to-stick* and *value-over-time*. It cannot honestly compute
the three §11 **labeled** KPIs the product `metrics` tool leaves `null` — `capture_rate`,
`regressions_prevented`, `retrieval_precision` — because ordinary runs have no ground truth. The
**calibration harness** supplies exactly that: a small hand-labeled set it scores against real
Whetstone.

```sh
python -m harness.calibrate [--kpi retrieval|capture|regressions|all]
```

- Labels live in [`calibration/labels.yaml`](calibration/labels.yaml) — a human vouches for each case.
- `retrieval_precision` and `capture_rate` are **key-free** (pure recall / capture over seeded
  stores). `regressions_prevented` uses a **key-free proxy** (the in-scope issue is recalled for a
  violating intent); a live `--agent` cold-vs-warm variant is the published number.
- Writes `out/calibration.json`; `metrics.py` folds it into `out/metrics.json`'s
  `showcase_only_kpis`, and the site shows real figures. **Hard boundary:** the runtime `metrics`
  tool STILL returns null for these — only the published showcase (linked to the labeled set) shows
  them. When `calibration.json` is absent the site falls back to the honest null-with-note.

## Layout

```
harness/
  config.py         pinned showcase environment (ST backend, isolated store, autonomous)
  schema.py         scenario dataclasses + validating loader; the harness<->site contract
  skills.py         per-skill SkillSpec registry (primary artifact, check language, prompt)
  skill/<name>/     one vendored Claude skill per dir, mounted by the --agent runner
  scenarios/        one *.yaml per scenario (each names its `skill:`)
  data/             input files scenarios reference (CSVs, design briefs)
  calibration/      labels.yaml — hand-labeled ground truth for the three §11 labeled KPIs (M5b)
  generate.py       stub + live Agent-SDK generators (both skill-driven)
  calibrate.py      computes capture_rate / regressions_prevented / retrieval_precision (M5b)
  out/<skill>/<scenario>/   generated, committed artifacts the site reads
  out/calibration.json      calibrated labeled-KPI numbers (M5b), read by metrics.py + the site
  run.py            cold/seed/warm runner
  metrics.py        aggregates out/**/summary.json -> out/metrics.json (per-skill + overall)
```
