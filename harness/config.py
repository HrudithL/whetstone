"""Showcase-harness configuration (M3).

This module pins the environment the *internal* showcase harness runs under. It is **not** part of
the distributed ``whetstone`` package and is never imported by the MCP server — it exists only so
the command-only harness produces trustworthy artifacts:

* **sentence-transformers backend, pinned.** The dedup/conflict/retrieval thresholds are calibrated
  for ST (see M2.5); the light ``hashing`` default lets paraphrased duplicates slip through and
  would make demos look sloppy. The harness always runs on ST.
* **An isolated store root.** Showcase runs seed a throwaway store under ``harness/.store/``
  (gitignored) so they never touch a real user store at ``~/.local/share/whetstone``.
* **Autonomous supervision.** Seeding replays scripted feedback through ``capture``/``revise``
  unattended, so the harness must not block on confirmation prompts.

Call :func:`showcase_env` to get the ``WHETSTONE_*`` overrides as a dict, or
:func:`apply_showcase_env` to set them on ``os.environ`` before driving the tools. The keys mirror
``whetstone.config.Config`` fields (env var = ``WHETSTONE_<FIELD_UPPER>``).
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo-relative anchor: harness/ lives at the repo root, alongside src/ and docs/.
HARNESS_ROOT = Path(__file__).resolve().parent

# The throwaway store the harness seeds while generating artifacts. Gitignored; each per-skill
# store under it is its own nested git repo, so it is never committed — the proof is harness/out/.
STORE_ROOT = HARNESS_ROOT / ".store"

# Pinned embedding backend + model for the showcase. Must match the M2.5-calibrated ST config.
EMBEDDING_BACKEND = "sentence-transformers"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Seeding must run unattended. `autonomous` clears the ordinary capture/revise confirmation gates,
# but promotion (learning -> issue at the recurrence threshold) and contradiction-removal ALWAYS
# confirm regardless of supervision mode, by design. The showcase never promotes or removes on
# contradiction, and the value-over-time scenarios reinforce a learning many times — so we also pin
# the promotion threshold above any realistic harness run count to keep reinforcement from ever
# reaching the promotion-suggestion branch. (Whetstone commits the reinforcement either way; this
# just avoids a `needs_confirmation` the runner would otherwise have to step over.)
SUPERVISION = "autonomous"
PROMOTION_THRESHOLD = 100000


def showcase_env() -> dict[str, str]:
    """Return the ``WHETSTONE_*`` env overrides that pin the showcase environment."""
    return {
        "WHETSTONE_EMBEDDING_BACKEND": EMBEDDING_BACKEND,
        "WHETSTONE_EMBEDDING_MODEL": EMBEDDING_MODEL,
        "WHETSTONE_STORE_ROOT": str(STORE_ROOT),
        "WHETSTONE_SUPERVISION": SUPERVISION,
        "WHETSTONE_PROMOTION_THRESHOLD": str(PROMOTION_THRESHOLD),
    }


def apply_showcase_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Pin the showcase environment on ``environ`` (defaults to ``os.environ``); return the pins.

    A showcase run must be reproducible regardless of the maintainer's shell, so this first **clears
    every** ``WHETSTONE_*`` var, then sets our pins. Clearing matters: ``whetstone.config`` consumes
    *all* ``WHETSTONE_*`` fields, so a stray override such as ``WHETSTONE_DEDUP_SIMILARITY`` or
    ``WHETSTONE_LEARNINGS_CUTOFF`` left in the environment would otherwise run the showcase on
    non-calibrated thresholds. After clearing, the tunables we do not pin fall back to the
    ST-calibrated dataclass defaults.
    """
    target = os.environ if environ is None else environ
    for key in [k for k in target if k.startswith("WHETSTONE_")]:
        del target[key]
    overrides = showcase_env()
    target.update(overrides)
    return overrides
