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

from dataclasses import dataclass

from .config import Config
from .embeddings import EmbeddingBackend, cosine
from .scoring import weight_for
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


@dataclass
class RecalledIssue:
    id: str
    rule: str
    scope: str


def _scope_similarity(query: list[float], scope: ScopeVectors) -> float:
    return max(cosine(query, scope.centroid), cosine(query, scope.phrase))


def _matched_scopes(query: list[float], scopes: list[ScopeVectors], cutoff: float) -> set[str]:
    return {s.scope for s in scopes if _scope_similarity(query, s) >= cutoff}


def _to_learning(entry: IndexedEntry) -> RecalledLearning:
    recurrence = entry.recurrence or 0
    return RecalledLearning(
        id=entry.id,
        rule=entry.body,
        scope=entry.scope,
        recurrence=recurrence,
        weight=round(weight_for(recurrence), 4),
    )


def _to_issue(entry: IndexedEntry) -> RecalledIssue:
    return RecalledIssue(id=entry.id, rule=entry.body, scope=entry.scope)


def _mmr(
    query: list[float], candidates: list[IndexedEntry], k: int, lam: float
) -> list[IndexedEntry]:
    """Maximal Marginal Relevance (§5.4): pick a diverse, high-value subset of size <= ``k``.

    Each step maximizes ``lam * (weight * sim_to_query) - (1 - lam) * max_sim_to_already_picked``.
    """
    remaining = [(e, cosine(query, e.vector)) for e in candidates]
    picked: list[IndexedEntry] = []
    while remaining and len(picked) < k:
        best_index = 0
        best_score = None
        for i, (entry, sim) in enumerate(remaining):
            relevance = weight_for(entry.recurrence or 0) * sim
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
) -> tuple[list[RecalledLearning], list[RecalledIssue]]:
    top_learnings = sorted(
        learnings, key=lambda e: weight_for(e.recurrence or 0), reverse=True
    )[:learnings_k]
    ranked = sorted(issue_scopes, key=lambda s: _scope_similarity(query, s), reverse=True)
    keep = {s.scope for s in ranked[:_FALLBACK_ISSUE_SCOPES]}
    broad_issues = [e for e in issues if e.scope in keep]
    return [_to_learning(e) for e in top_learnings], [_to_issue(e) for e in broad_issues]


def retrieve(
    loc: StoreLocation,
    intent: str,
    backend: EmbeddingBackend,
    config: Config,
    learnings_k: int | None = None,
) -> tuple[list[RecalledLearning], list[RecalledIssue]]:
    """Retrieve the learnings and issues relevant to ``intent`` (assumes the index is fresh)."""
    if learnings_k is None:
        learnings_k = config.learnings_k
    # Clamp so a negative cap (a bad caller or WHETSTONE_LEARNINGS_K=-1) can't hit Python's
    # negative-slice semantics on the fallback path and flood the payload.
    learnings_k = max(0, learnings_k)

    query = backend.embed([intent])[0]

    learning_scopes = index.load_scopes(loc, "learning")
    issue_scopes = index.load_scopes(loc, "issue")
    learnings = index.load_entries(loc, "learning")
    issues = index.load_entries(loc, "issue")

    matched_learning = _matched_scopes(query, learning_scopes, config.learnings_cutoff)
    matched_issue = _matched_scopes(query, issue_scopes, config.issues_cutoff)

    if not matched_learning and not matched_issue:
        return _fallback(query, learnings, issues, issue_scopes, learnings_k)

    in_scope_learnings = [e for e in learnings if e.scope in matched_learning]
    in_scope_issues = [e for e in issues if e.scope in matched_issue]

    picked = _mmr(query, in_scope_learnings, learnings_k, config.mmr_lambda)
    return [_to_learning(e) for e in picked], [_to_issue(e) for e in in_scope_issues]
