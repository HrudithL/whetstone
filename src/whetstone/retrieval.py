"""Scope-based retrieval over the index (§5.4): scope match -> MMR cap -> fallback floor.

Given the model's *elaborated intent* (never the raw prompt — that closes the abstraction gap,
§5.4), embed it and:

1. **Scope match** — a scope matches when ``max(sim(q, centroid), sim(q, phrase))`` clears its
   cutoff for ANY of the intent's query vectors: the full intent, plus each of its top-level
   comma/semicolon-separated clauses (see ``_intent_clauses``). A single-topic intent behaves
   exactly as before (nothing to split); a multi-topic intent — e.g. "color palette, axis scales,
   legend placement" — pools into one sentence embedding whose per-topic signal dilutes as more
   topics are named, so matching each clause too recovers scopes the pooled vector alone would
   miss. Learnings and issues have separate, asymmetric cutoffs (issues lower: including a
   marginally-relevant mandatory "don't do X" is cheap).
2. **Learnings** from matched scopes are capped to ``learnings_k`` by MMR (diverse, not k
   near-duplicates); **issues** from matched scopes are returned uncapped (all are mandatory). MMR
   ranking, relevance, and weight all key off the full intent only — clause-splitting affects
   which scopes are eligible, never how the eligible entries are ranked/picked.
3. **Fallback floor** — if *no* scope clears either cutoff (under any clause), return the
   top-weight learnings plus broadly-relevant issues so a real-but-thin request never comes back
   empty.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
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


@dataclass
class RetrievalSnapshot:
    """§M7b: a copy of the exact index rows one ``retrieve()`` call read, for a caller that needs to
    inspect entries beyond what ``RecalledLearning``/``RecalledIssue`` carry (e.g. `server.recall`'s
    post-hoc conflict pass, which needs each returned entry's title/body/vector/scope).

    Pass ``snapshot_out=RetrievalSnapshot()`` to ``retrieve()`` and it is filled in place; every
    existing caller omits it and sees byte-identical behavior (opt-in, keyword-only, no change to
    scope-matching/cutoff/MMR/fallback logic). ``entries`` holds ONLY the entries this call
    actually returned (picked/matched-scope, or the fallback floor's picks) — never the whole
    store — keyed by id. ``scope_phrase`` is scope name -> phrase vector, reusing the scope
    vectors this call already loaded (no extra query), for a scope-overlap check mirroring
    `_find_conflict`'s.

    Both are captured from the single connection this ``retrieve()`` call opened, so a caller that
    reads this snapshot analyzes the SAME data the payload was built from — a concurrent
    capture/revise index rebuild that lands after this call returns can't produce an analysis
    inconsistent with what was actually returned.
    """

    entries: dict[str, IndexedEntry] = field(default_factory=dict)
    scope_phrase: dict[str, list[float]] = field(default_factory=dict)


def _scope_similarity(query: list[float], scope: ScopeVectors) -> float:
    return max(cosine(query, scope.centroid), cosine(query, scope.phrase))


# An elaborated intent that legitimately spans several styling dimensions (§5.4's own worked
# example is itself a comma list: "color palette + row banding, number/currency formatting,
# column alignment, header emphasis, density") pools into ONE sentence embedding whose per-topic
# signal gets diluted as more topics are named — a 6-dimension sentence's vector sits roughly
# equidistant from all 6 scopes, none of them close enough to individually clear a cutoff tuned
# against single-topic calibration intents. Splitting on top-level enumeration/sentence punctuation
# and matching each clause too (in ADDITION to the whole intent, never instead of it) recovers the
# per-dimension signal a pooled vector drowns out, without changing what a single-clause intent
# already matched. This is the fix the design doc itself calls for: "No threshold value fixes the
# abstraction gap; fixing the query does" (§5.4 point 1). Sentence-ending periods split too, not
# just commas/semicolons: an intent that leads with a multi-sentence task description before naming
# its dimensions (e.g. "...Produce a single self-contained index.html. Consider color palette and
# accent, typography, ...") would otherwise leave that first dimension's clause glued to the entire
# preamble — measured to sit right at the cutoff's edge, while every later comma-bounded dimension
# clears it easily; splitting on a sentence-ending "." too isolates it the same way. Only a period
# followed by whitespace-then-uppercase (a new sentence) or whitespace-then-end-of-string counts as
# a boundary — a bare `.` (caught by review, not hypothetical: "Set opacity to 0.5" would otherwise
# produce the bogus, truncated probe "Set opacity to 0") does not, so numbers, filenames, and
# abbreviations like "index.html" or "e.g." stay intact.
_CLAUSE_SPLIT_RE = re.compile(r"[,;]|\.(?=\s+[A-Z]|\s*$)")

# A real elaborated intent (per-skill dimension lists in this repo, and §5.4's own worked example)
# names on the order of 5-7 topics; this leaves generous headroom while bounding the embedding work
# a single `recall` call can trigger. `intent` is a caller-controlled MCP argument — with no cap, a
# pathological or just very long, heavily-punctuated intent would blow the clause list up to one
# entry per punctuation mark, and every entry costs a full `backend.embed` vector (real memory/CPU,
# especially on the sentence-transformers backend's `encode`) plus an `O(clauses × scopes)` scope
# comparison — caught by Codex review, not hypothetical for a caller that isn't the well-behaved
# harness. Capped at the FULL INTENT plus the first 15 usable clauses (16 embeddings total).
_MAX_CLAUSES = 16


def _intent_clauses(intent: str) -> list[str]:
    """``intent`` plus up to ``_MAX_CLAUSES - 1`` of its top-level comma/semicolon/period-separated
    clauses, deduped.

    Returns just ``[intent]`` when there is no USABLE clause distinct from the intent itself (see
    the word-count filter below) — a single-topic intent is embedded and matched exactly as before.
    Otherwise every usable clause is embedded IN ADDITION to the full sentence — including when
    exactly one survives filtering — so scope-matching only ever gains candidates relative to the
    whole-intent-only baseline, never loses one (short of the cap below). An earlier version bailed
    out to ``[intent]`` whenever fewer than two clauses survived filtering, which silently discarded
    the one usable clause a two-clause intent like ``"caps, header emphasis"`` reduces to (only
    "header emphasis" passes the word-count filter) — a real, caught-by-review regression back into
    the exact dilution this function exists to fix.

    A single bare word ("caps", "emphasis") carries no context once split out on its own and, on
    the calibration labeled set, was measured to spuriously drift into an unrelated scope's cutoff
    (a real precision regression, not a hypothetical one) — dropped rather than treated as its own
    probe. Every dimension this fix actually targets (e.g. "legend placement", "color palette and
    encoding") is itself 2+ words, so this costs none of the intended recall.

    One more calibration-measured case: when exactly one clause survives the word-count filter AND
    it is a literal PREFIX of the intent (i.e. splitting only ever trimmed short trailing fragments
    off the end — "<lead>: header weight" out of "<lead>: header weight, caps, emphasis"), it isn't
    a distinct sub-topic, just the intent restated minus a couple of one-word tails, and embedding
    it separately was measured to spuriously drift into an unrelated scope's cutoff the same way a
    bare word does — so that one case also falls back to ``[intent]``. This does NOT apply when
    several clauses survive (a first clause that happens to lead the intent, e.g. "Styling a table:
    color palette" out of "Styling a table: color palette; row banding, currency formatting", is
    still a genuine, useful sub-topic there — the prefix relationship alone only disqualifies a
    SOLE survivor, where it is the only signal an already-thin split produced).
    """
    raw_parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(intent) if p.strip()]
    usable = [p for p in raw_parts if len(p.split()) >= 2]
    if not usable or (len(usable) == 1 and intent.startswith(usable[0])):
        return [intent]
    seen = {intent}
    clauses = [intent]
    for p in usable:
        if len(clauses) >= _MAX_CLAUSES:
            break
        if p not in seen:
            seen.add(p)
            clauses.append(p)
    return clauses


def _matched_scopes(
    queries: list[list[float]], scopes: list[ScopeVectors], cutoff: float
) -> set[str]:
    """A scope matches if ANY query vector (the full intent, or one of its clauses) clears
    cutoff."""
    return {
        s.scope for s in scopes if max(_scope_similarity(q, s) for q in queries) >= cutoff
    }


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
    snapshot_out: RetrievalSnapshot | None = None,
) -> tuple[list[RecalledLearning], list[RecalledIssue]]:
    top_learnings = sorted(
        learnings, key=lambda e: _entry_weight(e, config, today), reverse=True
    )[:learnings_k]
    ranked = sorted(issue_scopes, key=lambda s: _scope_similarity(query, s), reverse=True)
    keep = {s.scope for s in ranked[:_FALLBACK_ISSUE_SCOPES]}
    broad_issues = [e for e in issues if e.scope in keep]
    if snapshot_out is not None:
        snapshot_out.entries.update({e.id: e for e in top_learnings})
        snapshot_out.entries.update({e.id: e for e in broad_issues})
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
    *,
    snapshot_out: RetrievalSnapshot | None = None,
) -> tuple[list[RecalledLearning], list[RecalledIssue]]:
    """Retrieve the learnings and issues relevant to ``intent`` (assumes the index is fresh).

    ``today`` is the reference date for the recency decay (§4.4); it defaults to the current UTC
    date and is injectable so tests can score against a fixed ``last_seen``. ``snapshot_out``
    (§M7b, keyword-only, opt-in) fills in a :class:`RetrievalSnapshot` with the raw entries/scope
    vectors this call read, for a caller that needs more than ``RecalledLearning``/``RecalledIssue``
    carry — every other caller omits it and the return value is unaffected.
    """
    if learnings_k is None:
        learnings_k = config.learnings_k
    # Clamp so a negative cap (a bad caller or WHETSTONE_LEARNINGS_K=-1) can't hit Python's
    # negative-slice semantics on the fallback path and flood the payload.
    learnings_k = max(0, learnings_k)
    if today is None:
        today = datetime.now(UTC).date()

    clauses = _intent_clauses(intent)
    embedded = backend.embed(clauses)
    query = embedded[0]  # the full intent, unchanged — MMR ranking/relevance/fallback use only this

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

    if snapshot_out is not None:
        # Scope-phrase vectors this call already loaded above — no extra query — for a §M7b
        # scope-overlap check on the entries this call is about to return.
        snapshot_out.scope_phrase.update({s.scope: s.phrase for s in learning_scopes})
        snapshot_out.scope_phrase.update({s.scope: s.phrase for s in issue_scopes})

    # Scope MATCHING (only) checks every clause, so a multi-topic intent's per-dimension signal
    # isn't drowned out by the others (see _intent_clauses). Ranking within the matched set (MMR,
    # relevance, the fallback floor) still runs against `query` alone, unaffected.
    matched_learning = _matched_scopes(embedded, learning_scopes, config.learnings_cutoff)
    matched_issue = _matched_scopes(embedded, issue_scopes, config.issues_cutoff)

    if not matched_learning and not matched_issue:
        return _fallback(
            query, learnings, issues, issue_scopes, learnings_k, config, today, snapshot_out
        )

    in_scope_learnings = [e for e in learnings if e.scope in matched_learning]
    in_scope_issues = [e for e in issues if e.scope in matched_issue]

    picked = _mmr(query, in_scope_learnings, learnings_k, config.mmr_lambda, config, today)
    if snapshot_out is not None:
        snapshot_out.entries.update({e.id: e for e in picked})
        snapshot_out.entries.update({e.id: e for e in in_scope_issues})
    return (
        [_to_learning(e, config, today) for e in picked],
        [_to_issue(e) for e in in_scope_issues],
    )
