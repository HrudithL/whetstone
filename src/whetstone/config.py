"""Whetstone configuration: a dataclass of tunables plus a TOML + env loader.

Precedence (lowest to highest): dataclass defaults < ``config.toml`` < ``WHETSTONE_*`` env vars.

Only ``store_root`` and ``supervision`` are exercised in milestone M0; the remaining keys are
declared with their documented defaults so the config surface is stable for later milestones.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from .paths import config_path, default_store_root

_SUPERVISION_MODES = ("supervised", "balanced", "autonomous")
_EMBEDDING_BACKENDS = ("hashing", "sentence-transformers")


@dataclass
class Config:
    """Runtime configuration for the Whetstone server."""

    supervision: str = "balanced"
    learnings_half_life_days: int = 180
    learnings_decay: bool = True
    learnings_k: int = 12
    mmr_lambda: float = 0.7
    # M5e — the learned global layer. When on, `recall` runs the SAME per-store retrieval over the
    # reserved `__global__` store too and unions the (origin-tagged) results, so a preference that
    # recurs across skills applies everywhere. Off makes the payload byte-identical to
    # per-skill-only recall (the one-line bisect switch, §M5e). Retrieval logic is unchanged.
    consult_global: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    # Which embedding implementation to use (see whetstone.embeddings). "hashing" is a small,
    # dependency-free, deterministic default that keeps the base install light and lets tests run
    # without torch/network; "sentence-transformers" selects the model named by ``embedding_model``.
    embedding_backend: str = "hashing"
    # Vector width for the hashing backend (ignored by sentence-transformers, whose model fixes it).
    embedding_dim: int = 384
    # All similarity thresholds below (cutoffs, dedup, conflict, scope-merge ε) are tuned for the
    # **sentence-transformers backend** — the intended production embedder. The default `hashing`
    # backend is a light, offline stand-in with weaker semantic resolution, so similar/opposed
    # phrases score lower under it and these thresholds fire less readily; install the
    # `[embeddings]` extra for real retrieval/dedup/conflict quality.
    #
    # Retrieval cutoffs (§5.4). PROVISIONAL / UNCALIBRATED defaults: the real values come from
    # calibration against a labeled (elaborated-intent -> relevant-scopes) set (future work). Issues
    # use the lower cutoff on purpose — erring toward including a mandatory "don't do X" is cheap.
    learnings_cutoff: float = 0.35
    issues_cutoff: float = 0.25
    # A capture whose embedding is within this cosine similarity of an existing same-scope entry
    # counts as a near-duplicate (§7). PROVISIONAL / UNCALIBRATED.
    dedup_similarity: float = 0.9
    # A new entry within this cosine similarity of an existing OPPOSITE-polarity entry in an
    # overlapping scope is surfaced as a cross-polarity conflict (§7). PROVISIONAL / UNCALIBRATED.
    conflict_similarity: float = 0.85
    # When a learning's recurrence reaches this, `capture`/`revise` prompt to promote it to a
    # mandatory issue (§6). Promotion always asks the user, regardless of supervision mode.
    promotion_threshold: int = 4
    # Recurrence a demoted issue-turned-learning is seeded with (§5.2 `revise` demote).
    demote_seed_recurrence: int = 3
    # Compaction thresholds (§7, §5.4, §15). All PROVISIONAL / UNCALIBRATED — like the retrieval
    # cutoffs, the real values come from calibration (future work).
    # A learning whose derived §4.4 weight (at compaction time) falls below this is retired (§15).
    # Issues are NEVER auto-retired (§7).
    retire_weight_threshold: float = 0.15
    # Two same-polarity scopes are merged (anti-fragmentation, §5.4) when their centroids are within
    # ε_c (cosine >= this) OR their name/phrase embeddings are within ε_n (cosine >= this).
    scope_merge_centroid_eps: float = 0.9
    scope_merge_name_eps: float = 0.9
    # M5a — behavioral mining thresholds for the `compact` pass (all advisory-report-only in v1).
    # A learning reinforced this many times and never weakened is a "harden" candidate (suggest
    # promoting it to an issue). PROVISIONAL / UNCALIBRATED.
    harden_reinforcements: int = 4
    # A learning `recall` has surfaced across at least this many runs without ever being reinforced
    # (or not surfaced at all across that many runs) is a usage-based "stale" nudge — richer than
    # pure weight decay. PROVISIONAL / UNCALIBRATED.
    stale_runs: int = 20
    # `compact --all` clusters near-duplicate learnings appearing in at least this many distinct
    # skills and promotes the cluster into the `__global__` layer (M5e). PROVISIONAL / UNCALIBRATED.
    global_skill_count: int = 3
    # M7c — SPIKE, OFF by default (experimental/opt-in). When a new learning near-dups an existing
    # one (already above `dedup_similarity`, same/close scope), also run a small, hand-picked,
    # explicitly non-exhaustive antonym/negation lexicon check over the two bodies before silently
    # reinforcing. If it detects an asymmetry (e.g. "left" on one side, "right" on the other; a
    # negation word on only one side), `capture` returns `possible_contradiction` instead of
    # reinforcing -- a signal only, nothing is written.
    # This scores 1.0 precision / 1.0 recall on `harness/calibration/labels.yaml`'s
    # `same_polarity_contradiction` set (both embedding backends) -- but that labeled set is, by
    # construction, matched against the lexicon it tests, so it is NOT strong evidence on its own.
    # Five rounds of independent (Codex) code review each found a real, distinct precision or
    # correctness gap the labeled set didn't surface (see LEARNING_SKILLS_DESIGN.md §7 and the PR
    # for the full story) -- every one was fixed, but that pattern itself is evidence about how much
    # a lexical heuristic like this can be trusted without a much larger/independent evaluation.
    # Defaulting OFF is the honest call given that pattern; flip to `True` to opt in.
    same_polarity_contradiction_check: bool = False
    store_root: Path = field(default_factory=default_store_root)

    def __post_init__(self) -> None:
        if self.supervision not in _SUPERVISION_MODES:
            raise ValueError(
                f"supervision must be one of {_SUPERVISION_MODES}, got {self.supervision!r}"
            )
        if self.embedding_backend not in _EMBEDDING_BACKENDS:
            raise ValueError(
                f"embedding_backend must be one of {_EMBEDDING_BACKENDS}, "
                f"got {self.embedding_backend!r}"
            )
        self.store_root = Path(self.store_root).expanduser()


def _coerce(name: str, raw: object) -> object:
    """Coerce a raw string/TOML value to the type of the ``Config`` field ``name``."""
    field_type = _FIELD_TYPES[name]
    if field_type is bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if field_type is int:
        return int(raw)
    if field_type is float:
        return float(raw)
    if field_type is Path:
        return Path(str(raw)).expanduser()
    return str(raw)


_FIELD_TYPES: dict[str, type] = {
    "supervision": str,
    "learnings_half_life_days": int,
    "learnings_decay": bool,
    "learnings_k": int,
    "mmr_lambda": float,
    "consult_global": bool,
    "embedding_model": str,
    "embedding_backend": str,
    "embedding_dim": int,
    "learnings_cutoff": float,
    "issues_cutoff": float,
    "dedup_similarity": float,
    "conflict_similarity": float,
    "promotion_threshold": int,
    "demote_seed_recurrence": int,
    "retire_weight_threshold": float,
    "scope_merge_centroid_eps": float,
    "scope_merge_name_eps": float,
    "harden_reinforcements": int,
    "stale_runs": int,
    "global_skill_count": int,
    "same_polarity_contradiction_check": bool,
    "store_root": Path,
}


def load_config(path: Path | None = None) -> Config:
    """Load configuration from TOML (if present) with ``WHETSTONE_*`` env overrides.

    ``path`` defaults to :func:`whetstone.paths.config_path`. A missing file is fine — the
    dataclass defaults apply.
    """
    values: dict[str, object] = {}

    toml_path = path if path is not None else config_path()
    if toml_path.exists():
        with toml_path.open("rb") as fh:
            data = tomllib.load(fh)
        for name in _FIELD_TYPES:
            if name in data:
                values[name] = _coerce(name, data[name])

    for f in fields(Config):
        env_key = f"WHETSTONE_{f.name.upper()}"
        if env_key in os.environ:
            values[f.name] = _coerce(f.name, os.environ[env_key])

    return Config(**values)
