"""Out-of-band store maintenance — the ``compact`` pass (§7 "Distill & reconcile").

Compaction is a periodic janitorial sweep that keeps a store lean. It is NOT one of the five MCP
tools (attach/recall/capture/revise/metrics); it runs out-of-band via ``whetstone compact <skill>``
or by calling :func:`compact` directly. The whole pass runs under the per-store write lock and, in
order (§7, §5.4, §15):

1. **Dedupe** — collapse near-duplicate same-scope entries (cosine >= ``dedup_similarity``) into
   one. This is a batch version of capture-time dedup: for learnings the survivor's recurrence
   sums the collapsed counts and its dates widen (earliest ``first_seen``, latest ``last_seen``);
   for issues (no scoring fields) the near-duplicate blocks are simply dropped, keeping one.
2. **Merge overlapping scopes** (anti-fragmentation, §5.4) — merge two same-polarity scopes when
   their centroids OR their name/phrase embeddings are within the configured ε. The smaller scope's
   entries are folded into the larger (which keeps its phrase as the canonical name); each moved
   entry's ``scope`` field is rewritten and the emptied source file removed. Done per-polarity.
3. **Retire stale learnings** (§15) — drop learnings whose derived §4.4 ``weight`` (evaluated at
   ``today``) falls below ``retire_weight_threshold``. **Issues are NEVER auto-retired** (§7).

After mutating the markdown the index is rebuilt, the store is git-committed once (a single
``compact: …`` commit), and a ``compaction`` telemetry event is emitted — but only when the pass
actually changed something, so a no-op compaction on a clean store leaves no commit or event behind.

Retired/collapsed ids are recorded via :func:`record_id` before their entries leave the markdown, so
compaction never reuses an id (the same no-reuse guarantee ``remove_entry`` gives).

TODO (§5.4): scope-merge/anti-fragmentation should also happen incrementally at capture time, so the
store never drifts far between compactions. This slice implements it only in the batch pass; the
capture-time variant is future work.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from .config import Config, load_config
from .embeddings import cosine, get_backend
from .scoring import weight
from .store import index
from .store.access import (
    load_issues,
    load_learnings,
    record_id,
    remove_entry,
    save_issue,
    save_learning,
)
from .store.index import _centroid, entry_text
from .store.layout import (
    StoreLocation,
    commit_store,
    ensure_store,
    store_location,
    store_write_lock,
)
from .store.markdown import (
    parse_issues,
    parse_learnings,
    write_issues,
    write_learnings,
)
from .store.slug import scope_filename
from .telemetry import emit_compaction


def compact(skill: str, *, today: date | None = None, config: Config | None = None) -> dict:
    """Run the compaction maintenance pass over ``skill``'s store (§7); return a summary.

    ``today`` is the reference date for the recency decay used to score learnings for retirement
    (§4.4); it defaults to the current UTC date and is injectable so tests are deterministic. The
    whole pass runs under the per-store write lock and commits at most once.
    """
    if config is None:
        config = load_config()
    if today is None:
        today = datetime.now(UTC).date()

    ensure_store(skill, config)
    loc = store_location(skill, config)
    backend = get_backend(config)

    with store_write_lock(loc):
        deduped = _dedup(loc, backend, config, "learning") + _dedup(loc, backend, config, "issue")
        merged = _merge_scopes(loc, backend, config, "learning") + _merge_scopes(
            loc, backend, config, "issue"
        )
        retired = _retire_stale_learnings(loc, config, today)

        changed = deduped + merged + retired
        committed = False
        if changed:
            index.rebuild_index(loc, backend)
            commit_store(
                loc,
                f"compact: deduped {deduped}, merged {merged} scope(s), retired {retired}",
            )
            emit_compaction(loc, retired=retired, merged_scopes=merged, deduped=deduped)
            committed = True

    return {
        "skill": skill,
        "deduped": deduped,
        "merged_scopes": merged,
        "retired": retired,
        "committed": committed,
    }


# --------------------------------------------------------------------------- dedupe (step 1)


def _dedup(loc: StoreLocation, backend, config: Config, polarity: str) -> int:
    """Collapse near-duplicate same-scope entries into one; return how many were removed.

    Works per scope file (each file holds exactly one scope). Within a file, greedily assign each
    entry to the first representative it is within ``dedup_similarity`` of, else it starts a new
    representative. For learnings the representative absorbs the duplicate's recurrence/dates; for
    issues the duplicate is just dropped. Removed ids are recorded so they are never reused.
    """
    if polarity == "learning":
        directory, parse, write = loc.learnings_dir, parse_learnings, write_learnings
    else:
        directory, parse, write = loc.issues_dir, parse_issues, write_issues

    deduped = 0
    for path in sorted(directory.glob("*.md")):
        entries = parse(path.read_text(encoding="utf-8"))
        if len(entries) < 2:
            continue
        vectors = backend.embed([entry_text(e.title, e.body) for e in entries])
        reps: list[list] = []  # [entry, vector] pairs kept as representatives
        removed = 0
        for entry, vec in zip(entries, vectors, strict=True):
            match = next(
                (r for r in reps if cosine(vec, r[1]) >= config.dedup_similarity), None
            )
            if match is None:
                reps.append([entry, vec])
                continue
            if polarity == "learning":
                match[0] = _absorb_learning(match[0], entry)
            record_id(loc, entry.id)  # remember the id before it leaves the markdown (no reuse)
            removed += 1
        if removed:
            write(path, [r[0] for r in reps])
            deduped += removed
    return deduped


def _absorb_learning(survivor, other):
    """Fold ``other`` into ``survivor``: sum recurrence, widen the date span (earliest first_seen,
    latest last_seen). The survivor's prose/scope/id/provenance are kept."""
    return replace(
        survivor,
        recurrence=survivor.recurrence + other.recurrence,
        first_seen=min(survivor.first_seen, other.first_seen),
        last_seen=max(survivor.last_seen, other.last_seen),
    )


# --------------------------------------------------------------------------- merge scopes (step 2)


def _merge_scopes(loc: StoreLocation, backend, config: Config, polarity: str) -> int:
    """Merge overlapping same-polarity scopes (§5.4); return how many scopes were folded away.

    Two scopes overlap when their centroids are within ε_c OR their name/phrase embeddings are
    within ε_n. Overlap is grouped transitively (union-find); within each group the scope with most
    entries becomes canonical and the rest are folded into it (entries moved, ``scope`` field
    rewritten, emptied source files removed). Ids are unchanged by a move, so no id is retired here.
    """
    if polarity == "learning":
        entries = load_learnings(loc)
        directory, save = loc.learnings_dir, save_learning
    else:
        entries = load_issues(loc)
        directory, save = loc.issues_dir, save_issue

    by_scope: dict[str, list] = {}
    for entry in entries:
        by_scope.setdefault(entry.scope, []).append(entry)
    scopes = sorted(by_scope)
    if len(scopes) < 2:
        return 0

    name_vecs = backend.embed(scopes)
    centroids = [
        _centroid(backend.embed([entry_text(e.title, e.body) for e in by_scope[s]]), backend.dim)
        for s in scopes
    ]

    parent = list(range(len(scopes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(len(scopes)):
        for j in range(i + 1, len(scopes)):
            if (
                cosine(centroids[i], centroids[j]) >= config.scope_merge_centroid_eps
                or cosine(name_vecs[i], name_vecs[j]) >= config.scope_merge_name_eps
            ):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(scopes)):
        groups.setdefault(find(i), []).append(i)

    merged = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        # Canonical target: most entries wins, scope name breaks ties (deterministic).
        target = max(members, key=lambda i: (len(by_scope[scopes[i]]), scopes[i]))
        target_scope = scopes[target]
        for i in members:
            if i == target:
                continue
            source_scope = scopes[i]
            for entry in by_scope[source_scope]:
                save(loc, replace(entry, scope=target_scope))  # writes into the target scope file
            (directory / scope_filename(source_scope)).unlink(missing_ok=True)
            merged += 1
    return merged


# --------------------------------------------------------------------------- retire (step 3)


def _retire_stale_learnings(loc: StoreLocation, config: Config, today: date) -> int:
    """Remove learnings whose derived §4.4 weight (at ``today``) is below the retire threshold.

    Issues are never scored and never retired (§7) — only learnings are considered. Removal goes
    through :func:`remove_entry`, which records the id first so it is never reused.
    """
    retired = 0
    for entry in load_learnings(loc):
        w = weight(
            entry.recurrence,
            entry.last_seen,
            today,
            decay=config.learnings_decay,
            half_life_days=config.learnings_half_life_days,
        )
        if w < config.retire_weight_threshold:
            remove_entry(loc, entry.id)
            retired += 1
    return retired
