# Whetstone MCP Server — Build Plan

> Private working notes (`.planning/` is gitignored per CONTRIBUTING.md §2). Source specs:
> [`LEARNING_SKILLS_DESIGN.md`](../LEARNING_SKILLS_DESIGN.md) (primary/active) and
> [`SKILL_IMPLEMENTATION_DESIGN.md`](../SKILL_IMPLEMENTATION_DESIGN.md) (deferred).

## Goal

Build **Whetstone**, a local MCP server that attaches to any existing skill and lets it continually
improve from ordinary use: capturing user taste in `LEARNINGS` (soft, weighted, decaying) and hard
rules in `ISSUES` (objective, mandatory, permanent), applying both upfront on every run (no separate
review step), and committing legible markdown to git under a user-chosen supervision level. No
benchmark, dataset, or eval harness is required to operate. Delivered per the M0–M4 milestone plan in
§16 of the primary doc. `great-tables` is the first test subject.

## Scope in

- The **MCP server only** (per primary doc §1/§17). Five tools: `recall`, `capture`, `revise`,
  `attach`, `metrics`.
- Two-store model, `recurrence`/`recency`/`weight` scoring (learnings only), scope-based embedding
  retrieval (elaborated intent → centroid+phrase match → asymmetric cutoffs → MMR cap → fallback
  floor), capture-contract, promotion/demotion, supervision dial, git versioning, `events.jsonl`
  telemetry + `metrics`, compaction + scope merging.
- M3 showcase docs site (before / learned-layer / after; KPIs; blinded LLM judge).
- M4: attach to a code-improvement skill and a context-organizing skill to prove generalization.

## Scope out

- The **file-native "skill" implementation** and the **A/B comparison** — deferred
  (`SKILL_IMPLEMENTATION_DESIGN.md`). Do not build; do not blend (the purity rule, deferred doc §3).
- Any mutation of a target skill's own `SKILL.md` — Whetstone never touches the base skill.
- Cloud/hosted embedding APIs — retrieval is local and offline.

## Assumptions (inferred; correct me if wrong)

- Codename **whetstone** is retained (repo + docs use it; doc says provisional but no rename given).
- Python package managed with a standard `pyproject.toml`; target **Python 3.11+** (system is 3.9 —
  a project venv/interpreter will be provisioned; `uv` is not installed and can be added if desired).
- Official **Model Context Protocol Python SDK** (`mcp`, FastMCP style) for the server.
- `all-MiniLM-L6-v2` (384-dim) via **sentence-transformers** for embeddings (user-chosen), swappable
  behind a config key.
- Store lives under the **XDG data dir**: `$XDG_DATA_HOME/whetstone/<skill>/` (default
  `~/.local/share/whetstone/...`), overridable by env/config. Each skill store is its own git repo.
- The user runs Codex auto-review on PRs (confirmed on PR #1); the emoji/marker to wait for is
  Codex's `### 💡 Codex Review` (or a 👍 reaction meaning "no suggestions").

## Decisions already resolved with the user (2026-07-16)

1. **Language/runtime:** Python.
2. **Embeddings:** sentence-transformers, model `all-MiniLM-L6-v2`, behind a swappable interface.
3. **Store location:** XDG data dir, per-skill git repo, overridable.
4. **Process:** full CONTRIBUTING.md ceremony from M0 (root branch, subagent-per-slice, PR-per-slice,
   Codex review loop, merge-up with merge commits).
5. **Root base:** merge docs → `main` first (PR #1), then cut the root branch off `main`.
6. **Codex doc fixes (PR #1):** all four applied (half-life reparameterization; `capture`
   `needs_confirmation` contract; file-native schema alignment; per-run event log for both A/B arms).

## M0 subjective items — RESOLVED with user (2026-07-16)

- **Python tooling:** plain `pip` + stdlib `venv`, build backend **hatchling**, PEP-621
  `pyproject.toml`, `pip install -e '.[dev]'`. No new global tooling. Target Python 3.11+.
- **Names:** distribution/package **`whetstone-mcp`**; the **MCP server id** hosts register is
  **`whetstone`**; store root **`~/.local/share/whetstone/`** (XDG). Import package: `whetstone`.
- **Config surface:** **TOML in XDG config** — `$XDG_CONFIG_HOME/whetstone/config.toml` with
  documented defaults; `WHETSTONE_*` env vars override. Keys cover supervision mode, decay
  half-life/toggles, retrieval cutoffs, MMR λ, `learnings_k`, embedding model, store root. (Land the
  full TOML surface in M0 scaffold since it's chosen; individual tunables become meaningful in M1/M2.)

## Subjective items still to escalate (per §10) — before the slice that touches each

- **On-disk block format details** beyond the doc's example (id scheme `L#`/`I#`, date format,
  bullet key names): naming/format. → confirm at M0 store-format slice.
- **Calibration constants** (learnings/issues cutoffs, ε_c/ε_n merge thresholds): the doc says these
  come from a labeled calibration set, not guesses. → M1: propose a calibration procedure + labeled
  set; escalate the target precision/recall and the resulting numbers.
- **Showcase site stack** (M3): static generator/framework choice = dependency + architecture. →
  escalate at M3.
- **M4 target skills** (which code skill, which context skill): selection. → escalate at M4.

## Branch tree sketch

```
main
 └── whetstone-mcp                     (root; only branch that PRs to main)
      ├── feat/m0-attach-store
      │    ├── feat/m0-scaffold        (pyproject, pkg skeleton, .gitignore, config, XDG layout)
      │    ├── feat/m0-store-format    (markdown parser/writer, entry schema, block contract)
      │    └── feat/m0-attach-tool     (attach tool, lazy store creation, git init/commit)
      ├── feat/m1-recall-capture
      │    ├── feat/m1-embeddings      (sentence-transformers wrapper, index.sqlite scope vectors)
      │    ├── feat/m1-retrieval       (centroid+phrase match, cutoffs, MMR, fallback floor)
      │    ├── feat/m1-recall-tool     (recall: elaborated intent, payload, capture_contract)
      │    └── feat/m1-capture-tool    (capture: distill, dedup, conflict, commit, event)
      ├── feat/m2-revise-scoring
      │    ├── feat/m2-scoring         (recurrence/recency/weight, half-life decay, toggles)
      │    ├── feat/m2-revise-tool     (reinforce/weaken/remove/promote/demote + confirm prompts)
      │    ├── feat/m2-supervision     (supervised/balanced/autonomous dial; gate in capture/revise)
      │    ├── feat/m2-telemetry       (events.jsonl schema + metrics tool KPIs)
      │    └── feat/m2-compaction      (dedupe, scope merge ε_c/ε_n, retire weight<0.15)
      ├── feat/m3-showcase             (docs site: before/learned/after, KPIs, blinded judge)
      └── feat/m4-generalize           (attach to a code skill, then a context skill)
```
Sub-branches within a feature are parallelizable via subagents where independent; serialize the
dependent ones (scaffold → everything; embeddings → retrieval → recall).

## Slice breakdown + acceptance criteria

### M0 — Attach + store
- **m0-scaffold**: `pyproject.toml`, `src/whetstone/` package skeleton, `.gitignore` (incl.
  `.planning/`, venvs, `__pycache__`, model caches), `config.py` with documented defaults, XDG path
  helpers. *Accept:* package imports; `python -m whetstone --help` (or console entry) runs; config
  defaults load; `.planning/` ignored; lint/format clean.
- **m0-store-format**: dataclasses for learning/issue entries; markdown reader/writer implementing
  the §5.1 block contract (split on `## `, `<id> · <title>` heading, bullet metadata, prose body);
  round-trip fidelity; `weight` never written. *Accept:* unit tests round-trip both stores incl.
  edge cases (multi-paragraph body, unicode, missing optional fields); malformed block raises a clear
  error; writes are atomic.
- **m0-attach-tool**: `attach(skill, path?)` scaffolds `<xdg>/whetstone/<skill>/` with
  `learnings/`, `issues/`, `.git/` (init + first commit), registers the skill; lazy creation so
  `recall`/`capture` work without explicit attach. *Accept:* attach twice is idempotent; store dir
  and git repo exist; MCP tool discoverable by a host; integration test drives it through the MCP
  protocol (stdio) end-to-end.

### M1 — Recall + capture loop
- **m1-embeddings**: embedding backend interface + sentence-transformers impl (lazy model load,
  offline, cached); `index.sqlite` with per-scope centroid + phrase vectors and entry metadata;
  rebuildable from markdown. *Accept:* embed is deterministic; index rebuild from markdown reproduces
  vectors; brute-force cosine correct on a fixture.
- **m1-retrieval**: scope match `max(sim(intent,centroid), sim(intent,phrase)) ≥ cutoff`
  (asymmetric: issues lower); MMR diverse cap (`λ=0.7`, `learnings_k=12`); issues uncapped; fallback
  floor. *Accept:* worked example from §5.4 returns the expected scopes; vague intent hits the
  fallback, not empty; MMR returns breadth not duplicates (test with near-dup fixtures).
- **m1-recall-tool**: `recall(skill, intent, learnings_k=12)` returns the §5.2 payload incl.
  `how_to_use` + `capture_contract`; description enforces elaborated intent. *Accept:* payload
  matches the documented shape; empty store returns empty (not error); `how_to_use`/`capture_contract`
  strings present and correct.
- **m1-capture-tool**: `capture(skill, polarity, body, scope, provenance, confirm=false)` — distill
  to a scoped rule, dedup (near-dup → reinforce), conflict detect (LEARNINGS↔ISSUES), supervision
  gate → `needs_confirmation`, write markdown, git commit, append event. *Accept:* new entry commits;
  near-dup reinforces (recurrence+1, last_seen refreshed) instead of adding; conflict returns
  `conflict` status; supervised mode returns `needs_confirmation` then commits on `confirm:true`.

### M2 — Revise + scoring + supervision + telemetry
- **m2-scoring**: `recurrence`→`r=1−1/(1+max(recurrence,0))`; `recency=exp(−ln2·Δ/H)`, H=180;
  `weight=r×recency` (decay ON) / `r` (OFF); per-store decay toggle. *Accept:* unit tests for the
  math incl. `recency=0.5` at Δ=H; decay-off path; weight never persisted.
- **m2-revise-tool**: `revise(skill, entry_id, action, confirm=false)` with
  reinforce/weaken/remove/promote/demote; weaken<0 → keep@1/remove prompt; promote always confirms;
  demote seeds recurrence 3; issue contradiction 3-way prompt. *Accept:* each action's state
  transition tested; all confirm gates return `needs_confirmation` with the correct prompt.
- **m2-supervision**: supervised/balanced(default)/autonomous; gate lives in `capture`/`revise`;
  promotion + contradiction-removals always prompt regardless of mode. *Accept:* mode matrix tested.
- **m2-telemetry**: `events.jsonl` append-only schema; `metrics(skill?)` computes §11 KPIs
  (repeat-correction rate, learnings-applied/%-survived, regressions-prevented, capture-rate,
  retrieval precision). *Accept:* events written on every mutating op; metrics computed on a fixture
  event log match expected values.
- **m2-compaction**: periodic dedupe, scope merge (centroids within ε_c OR name-embeddings within
  ε_n), retire learnings with `weight<0.15`; issues never auto-retired. *Accept:* merge collapses
  "currency"/"currency columns"; stale learning retired; issues untouched.

### M3 — Showcase
- Docs site with, per curated example: **Before** / **learned layer** / **After** side by side;
  telemetry KPIs; blinded fixed-rubric LLM judge (independent of logged learnings). One example per
  skill class in priority order (visual → code → context). *Accept:* site builds; a `great-tables`
  example renders before/after visibly different; judge runs blinded; KPIs shown from real events.

### M4 — Generalize
- Attach to a **code-improvement** skill (objective ground truth: tests/lint/types), then a
  **context-organizing** skill; confirm the substrate holds with no skill-specific server code.
  *Accept:* both attach and complete a capture→recall→apply loop with zero changes to core tools.

## Risks / rollback

- **Retrieval quality hinges on elaborated intent + calibrated cutoffs.** Mitigate: enforce
  elaboration in tool descriptions; build the labeled calibration set early in M1; fallback floor
  prevents empty returns. Rollback: cutoffs/λ/k are config, tunable without code changes.
- **sentence-transformers/torch install weight & Python 3.9→3.11 gap.** Mitigate: pin versions,
  lazy-load the model, cache it; provision a project venv. Rollback: embedding backend is an
  interface — a lighter backend (e.g. fastembed) can be swapped without touching retrieval.
- **Capture-rate is model-behavior-dependent** (a missed capture just fails to record, never ships a
  wrong output — graceful degradation, §6). Mitigate: measure capture-rate; strong `capture_contract`.
- **Git-per-skill-store concurrency / partial writes.** Mitigate: atomic file writes + a single
  commit per op; treat the store repo as append-mostly.
- **Every store mutation is a git commit** → free rollback/audit (§10). A bad entry is revertible.
- **Codex may not review some PRs.** Per §6, if no review appears after a reasonable wait, ask the
  user how to handle review for that PR rather than inventing a substitute.

## Immediate next steps

1. PR #1 (docs → main): Codex re-review clean → get explicit user approval → merge (merge commit).
2. Cut `whetstone-mcp` root off updated `main`.
3. Escalate the M0 tooling/naming/config subjective items, then start `feat/m0-scaffold`.
