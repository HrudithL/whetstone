# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project does not yet follow strict
semantic versioning (pre-1.0).

## [Unreleased]

- Generalized the showcase harness beyond `great-tables` to `frontend-design`, `pptx`, and
  `plotnine` (3 skill classes), with committed live-agent artifacts and per-skill metrics.
- Added the learned **global layer** (`__global__` store): a cross-skill preference, consulted
  during `recall` alongside the skill's own store, fed by `compact --all` cluster detection and
  manual `whetstone promote`.
- Added `compact`'s advisory behavioral-mining pass (harden/bad-capture/stale/conflict-residue
  findings over `events.jsonl`), a calibration harness (`harness/calibrate.py`) computing real
  capture-rate/regression/retrieval-precision KPIs against a labeled set, preference packs
  (`whetstone export`/`import`), and `whetstone doctor` (read-only health check for the learned
  loop).
- Hardened cross-skill promotion integrity: global-promotion now requires explicit consent
  (`compact --all` only reports candidates; `promote --cluster` enacts them), `recall` surfaces
  cross-polarity conflicts directly, and capture gained a same-polarity antonym/negation heuristic
  to flag likely contradictions.
- Fixed a real retrieval bug where a multi-dimension intent's pooled embedding diluted per-topic
  signal, silently dropping scopes that should have matched; fixed inconsistently-authored
  learning/issue polarity in several scenarios; loosened brittle harness checks that produced false
  negatives on real (but differently-shaped) live-model output.
- Redesigned the Quarto showcase site (theme, landing page, docs content) and added a manual-review
  fallback to `CONTRIBUTING.md` for when the automated Codex review is rate-limited.

## [0.1.0] — first PyPI release

- Initial `whetstone-mcp` release: the five-tool MCP surface (`attach`, `recall`, `capture`,
  `revise`, `metrics`), git-tracked per-skill markdown stores, scoring/decay, the supervision dial,
  cross-polarity conflict detection, and `whetstone compact`.
- Dual embedding backends (`hashing` default, `sentence-transformers` opt-in via the `[embeddings]`
  extra) with CI running both.
- PyPI packaging (Trusted Publishing / OIDC release workflow), MIT license.
