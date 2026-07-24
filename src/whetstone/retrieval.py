"""Scope-based retrieval over the index (§5.4): scope match -> MMR cap -> fallback floor.

Given the model's *elaborated intent* (never the raw prompt — that closes the abstraction gap,
§5.4), embed it once and:

1. **Scope match** — a scope matches when ``max(sim(intent, centroid), sim(intent, phrase))`` clears
   its cutoff. Learnings and issues have separate, asymmetric cutoffs (issues lower: including a
   marginally-relevant mandatory "don't do X" is cheap).
2. **Learnings** from matched scopes are capped to ``learnings_k`` by MMR (diverse, not k
   near-duplicates); **issues** from matched scopes are returned uncapped (all are mandatory).
3. **Fallback floor** — if *no* scope clears either cutoff, return the top-weight learnings plus
   broadly-relevant issues so a real-but-thin request never comes back empty.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

from .config import Config
from .embeddings import EmbeddingBackend, cosine
from .scoring import weight
from .store import index
from .store.index import IndexedEntry, ScopeVectors
from .store.layout import StoreLocation

# How many nearest issue scopes seed the fallback floor. Issues are cheap to include but dumping the
# whole catalog on an off-topic intent is noise, so the floor surfaces the closest few "broadly
# relevant" scopes rather than everything. Provisional (see §5.4 calibration).
_FALLBACK_ISSUE_SCOPES = 3


@dataclass
class RecalledLearning:
    id: str
    rule: str
    scope: str
    recurrence: int
    weight: float
    # Which store this came from (§M5e): "skill" (this skill's own store) or "global" (the learned
    # cross-skill layer). Defaults to "skill" so `retrieve()` is untouched — the global-origin tag
    # is stamped by the recall orchestration in the server, never inside retrieval.
    origin: str = "skill"


@dataclass
class RecalledIssue:
    id: str
    rule: str
    scope: str
    origin: str = "skill"


def _scope_similarity(query: list[float], scope: ScopeVectors) -> float:
    return max(cosine(query, scope.centroid), cosine(query, scope.phrase))


def _matched_scopes(query: list[float], scopes: list[ScopeVectors], cutoff: float) -> set[str]:
    return {s.scope for s in scopes if _scope_similarity(query, s) >= cutoff}


def _entry_weight(entry: IndexedEntry, config: Config, today: date) -> float:
    """The full §4.4 weight for a learning entry: ``r × recency`` (decay on) or ``r`` (decay off).

    ``last_seen`` is parsed from its ISO string; if it is missing (defensive — the parser always
    supplies one), ``today`` is used so recency is 1 and the weight falls back to the recurrence
    term alone.
    """
    last_seen = date.fromisoformat(entry.last_seen) if entry.last_seen else today
    return weight(
        entry.recurrence or 0,
        last_seen,
        today,
        decay=config.learnings_decay,
        half_life_days=config.learnings_half_life_days,
    )


def _to_learning(entry: IndexedEntry, config: Config, today: date) -> RecalledLearning:
    return RecalledLearning(
        id=entry.id,
        rule=entry.body,
        scope=entry.scope,
        recurrence=entry.recurrence or 0,
        weight=round(_entry_weight(entry, config, today), 4),
    )


def _to_issue(entry: IndexedEntry) -> RecalledIssue:
    return RecalledIssue(id=entry.id, rule=entry.body, scope=entry.scope)


def _mmr(
    query: list[float],
    candidates: list[IndexedEntry],
    k: int,
    lam: float,
    config: Config,
    today: date,
) -> list[IndexedEntry]:
    """Maximal Marginal Relevance (§5.4): pick a diverse, high-value subset of size <= ``k``.

    Each step maximizes ``lam * (weight * sim_to_query) - (1 - lam) * max_sim_to_already_picked``,
    where ``weight`` is the full §4.4 weight (recurrence × recency), so a stale learning is
    down-weighted in the relevance term just as it is in the surfaced payload.
    """
    remaining = [(e, cosine(query, e.vector)) for e in candidates]
    picked: list[IndexedEntry] = []
    while remaining and len(picked) < k:
        best_index = 0
        best_score = None
        for i, (entry, sim) in enumerate(remaining):
            relevance = _entry_weight(entry, config, today) * sim
            diversity = max((cosine(entry.vector, p.vector) for p in picked), default=0.0)
            score = lam * relevance - (1.0 - lam) * diversity
            if best_score is None or score > best_score:
                best_score = score
                best_index = i
        picked.append(remaining.pop(best_index)[0])
    return picked


def _fallback(
    query: list[float],
    learnings: list[IndexedEntry],
    issues: list[IndexedEntry],
    issue_scopes: list[ScopeVectors],
    learnings_k: int,
    config: Config,
    today: date,
) -> tuple[list[RecalledLearning], list[RecalledIssue]]:
    top_learnings = sorted(
        learnings, key=lambda e: _entry_weight(e, config, today), reverse=True
    )[:learnings_k]
    ranked = sorted(issue_scopes, key=lambda s: _scope_similarity(query, s), reverse=True)
    keep = {s.scope for s in ranked[:_FALLBACK_ISSUE_SCOPES]}
    broad_issues = [e for e in issues if e.scope in keep]
    return (
        [_to_learning(e, config, today) for e in top_learnings],
        [_to_issue(e) for e in broad_issues],
    )


def retrieve(
    loc: StoreLocation,
    intent: str,
    backend: EmbeddingBackend,
    config: Config,
    learnings_k: int | None = None,
    today: date | None = None,
) -> tuple[list[RecalledLearning], list[RecalledIssue]]:
    """Retrieve the learnings and issues relevant to ``intent`` (assumes the index is fresh).

    ``today`` is the reference date for the recency decay (§4.4); it defaults to the current UTC
    date and is injectable so tests can score against a fixed ``last_seen``.
    """
    if learnings_k is None:
        learnings_k = config.learnings_k
    # Clamp so a negative cap (a bad caller or WHETSTONE_LEARNINGS_K=-1) can't hit Python's
    # negative-slice semantics on the fallback path and flood the payload.
    learnings_k = max(0, learnings_k)
    if today is None:
        today = datetime.now(UTC).date()

    query = backend.embed([intent])[0]

    # All four reads share ONE open connection so a concurrent capture/revise index rebuild (atomic
    # os.replace) can't straddle them — the open handle keeps reading its snapshot's inode, so every
    # query sees a single consistent index version rather than a mix of pre-/post-rebuild rows.
    conn = sqlite3.connect(str(index.index_path(loc)))
    try:
        learning_scopes = index.load_scopes(loc, "learning", conn)
        issue_scopes = index.load_scopes(loc, "issue", conn)
        learnings = index.load_entries(loc, "learning", conn)
        issues = index.load_entries(loc, "issue", conn)
    finally:
        conn.close()

    matched_learning = _matched_scopes(query, learning_scopes, config.learnings_cutoff)
    matched_issue = _matched_scopes(query, issue_scopes, config.issues_cutoff)

    if not matched_learning and not matched_issue:
        return _fallback(query, learnings, issues, issue_scopes, learnings_k, config, today)

    in_scope_learnings = [e for e in learnings if e.scope in matched_learning]
    in_scope_issues = [e for e in issues if e.scope in matched_issue]

    picked = _mmr(query, in_scope_learnings, learnings_k, config.mmr_lambda, config, today)
    return (
        [_to_learning(e, config, today) for e in picked],
        [_to_issue(e) for e in in_scope_issues],
    )
