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

Each scenario pairs a great-tables task (from the sibling `gtskill` corpus) with one or more
arbitrary subjective preferences (see [`schema.py`](schema.py)). Per scenario the runner (slice 3):

1. **COLD** — generates a table with an **empty** Whetstone store (the preference is typically not
   honored).
2. **Seed** — replays the scenario's scripted feedback through Whetstone's `capture`/`revise` tools,
   turning the preference into a tracked learning/issue (committed to the store, logged to
   `events.jsonl`).
3. **WARM** — regenerates with the `recall()` payload injected, and iterates to measure
   runs-to-stick; reads the weight trajectory for value-over-time.

Table generation adapts `gtskill`'s Claude-Agent-SDK path (CSV + prompt + great-tables skill →
`table.py`/`table.png`), so a run drives a live model and needs `ANTHROPIC_API_KEY` — which is
exactly why it is command-only and its outputs are committed.

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
export ANTHROPIC_API_KEY=sk-ant-...        # or put it in harness/.env (gitignored)
python -m harness.run                       # slice 3 — regenerates out/
```

## Layout

```
harness/
  config.py         pinned showcase environment (ST backend, isolated store, autonomous)
  schema.py         scenario dataclasses + validating loader; the harness<->site contract
  scenarios/        one *.yaml per scenario (authored in slice 2)
  out/              generated, committed artifacts the site reads (populated in slices 3-4)
  run.py            cold/warm runner (slice 3)
```
