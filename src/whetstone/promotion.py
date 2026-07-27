"""Promoting a preference into the learned global layer (§M5e).

A learning or issue that has proven itself *across skills* (or that a user lifts deliberately) is
moved out of its per-skill store into the reserved ``__global__`` store, where ``recall`` consults
it for every skill. This module is the **writer** half of the global layer:

- :func:`promote_to_global` — lift ONE entry from a skill store (manual ``whetstone promote``).
- :func:`promote_cluster` — enact ONE cross-skill cluster that ``compact --all`` reported as a
  ``global_candidate`` finding (manual ``whetstone promote <skill> <id> --cluster``, §M7a).
  ``compact --all`` itself only ever detects and reports these — it never writes (promotion always
  asks a human, the same rule the rest of Whetstone already holds).
- :func:`write_global_entry` / :func:`retire_source` — the shared building blocks both promotion
  paths above use to actually write the global entry and retire the per-skill copies.

Ids are **always re-minted** in the global store — a foreign per-skill id is never trusted (the same
no-reuse discipline the rest of the store keeps). Two (or more, for a cluster) stores are mutated
(global + the source skill(s)); write locks are always taken in a fixed order (global first, then
each skill) so concurrent promotions can never deadlock.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace

from .config import Config, load_config
from .embeddings import get_backend
from .store import index
from .store.access import (
    find_issue,
    find_learning,
    next_id,
    record_id,
    remove_entry,
    save_issue,
    save_learning,
)
from .store.entries import IssueEntry, LearningEntry
from .store.layout import (
    GLOBAL_SLUG,
    StoreLocation,
    commit_store,
    ensure_store,
    global_store_location,
    store_location,
    store_write_lock,
)
from .telemetry import emit_promote


@contextmanager
def _both_locks(g_loc: StoreLocation, skill_loc: StoreLocation):
    """Hold the global and skill write locks in a fixed (global-first) order to avoid deadlock."""
    with store_write_lock(g_loc), store_write_lock(skill_loc):
        yield


def write_global_entry(
    g_loc: StoreLocation,
    backend,
    entry: LearningEntry | IssueEntry,
    source_skill: str,
) -> str:
    """Write ``entry`` into the global store under a freshly-minted id; commit; return the new id.

    Recurrence/dates carry over for a learning; the provenance is annotated with where it came from.
    Assumes the global write lock is held and the global store exists.
    """
    polarity = "learning" if isinstance(entry, LearningEntry) else "issue"
    new_id = next_id(g_loc, polarity)
    provenance = f"promoted from {source_skill}: {entry.provenance}".strip()
    if isinstance(entry, LearningEntry):
        save_learning(g_loc, replace(entry, id=new_id, provenance=provenance))
    else:
        save_issue(g_loc, replace(entry, id=new_id, provenance=provenance))
    record_id(g_loc, new_id)
    index.rebuild_index(g_loc, backend)
    commit_store(g_loc, f"promote: add {new_id} (from {source_skill})")
    emit_promote(
        g_loc,
        source_skill=source_skill,
        source_id=entry.id,
        global_id=new_id,
        polarity=polarity,
    )
    return new_id


def retire_source(skill_loc: StoreLocation, backend, entry_id: str) -> None:
    """Remove a promoted entry from its source skill store and re-commit. Lock assumed held."""
    if remove_entry(skill_loc, entry_id):
        index.rebuild_index(skill_loc, backend)
        commit_store(skill_loc, f"promote: retire {entry_id} (promoted to global)")


def promote_to_global(skill: str, entry_id: str, config: Config | None = None) -> dict:
    """Lift a single learning/issue from ``skill`` into the global layer (§M5e).

    Re-mints the id in the global store, retires the per-skill copy, commits both stores. Returns a
    summary: ``skill``, ``source_id``, ``global_id``, ``polarity``.
    """
    if config is None:
        config = load_config()
    if skill == GLOBAL_SLUG:
        raise ValueError("cannot promote from the global store to itself")

    ensure_store(skill, config)
    ensure_store(GLOBAL_SLUG, config)
    skill_loc = store_location(skill, config)
    g_loc = global_store_location(config)
    backend = get_backend(config)

    with _both_locks(g_loc, skill_loc):
        index.rebuild_index_if_stale(skill_loc, backend)
        entry: LearningEntry | IssueEntry | None = find_learning(skill_loc, entry_id)
        if entry is None:
            entry = find_issue(skill_loc, entry_id)
        if entry is None:
            raise ValueError(f"no entry with id {entry_id!r} in skill {skill!r}")
        polarity = "learning" if isinstance(entry, LearningEntry) else "issue"
        global_id = write_global_entry(g_loc, backend, entry, skill)
        retire_source(skill_loc, backend, entry_id)

    return {
        "skill": skill,
        "source_id": entry_id,
        "global_id": global_id,
        "polarity": polarity,
    }


def promote_cluster(skill: str, entry_id: str, config: Config | None = None) -> dict:
    """Enact one cross-skill promotion candidate reported by ``compact --all`` (§M7a).

    ``skill``/``entry_id`` name the *representative* entry of a ``global_candidate`` finding (the
    same deterministic representative :func:`whetstone.compaction.cluster_representative` picks).
    Re-runs the same cross-skill clustering detection, restricted to whichever cluster contains
    that entry, then performs the write ``compact --all`` used to do automatically: the
    representative is written into the global store and every cluster member — across all its
    skills — is retired from its per-skill store. This is the only place a cross-skill cluster is
    actually promoted; ``compact --all`` itself only ever detects and reports.

    Raises ``ValueError`` if no current cluster containing ``(skill, entry_id)`` meets
    ``global_skill_count`` (e.g. the candidate is stale — the store changed since it was reported,
    or the entry doesn't exist), or if the representative was already enacted by a concurrent
    ``promote_cluster`` call for the same cluster (detected between locks — see below).
    """
    if config is None:
        config = load_config()
    if skill == GLOBAL_SLUG:
        raise ValueError("cannot promote from the global store to itself")

    # Lazy import: compaction.py imports from this module at load time, so importing it back at
    # module level here would create a circular import. Deferring to call time breaks the cycle.
    from .compaction import cluster_representative, find_cross_skill_clusters

    backend = get_backend(config)
    clusters = find_cross_skill_clusters(config, backend)
    cluster = next(
        (c for c in clusters if any(s == skill and e.id == entry_id for s, e in c)), None
    )
    if cluster is None:
        raise ValueError(
            f"no cross-skill cluster containing {entry_id!r} in skill {skill!r} meets "
            f"global_skill_count={config.global_skill_count} right now — the candidate may be "
            "stale; re-run `compact --all` to get a fresh finding"
        )

    ensure_store(GLOBAL_SLUG, config)
    g_loc = global_store_location(config)

    with store_write_lock(g_loc):
        index.rebuild_index_if_stale(g_loc, backend)
        rep_skill, rep_entry = cluster_representative(cluster)

        # The detection above ran before any lock was held, so a concurrent `promote_cluster` for
        # this same cluster could have already enacted it in between. The global lock serializes
        # racing promotions from here on, so re-check the representative still exists in its
        # source store now that we hold it — a fresh `find_learning`, not the possibly-stale entry
        # `find_cross_skill_clusters` returned.
        rep_loc = store_location(rep_skill, config)
        with store_write_lock(rep_loc):
            index.rebuild_index_if_stale(rep_loc, backend)
            fresh_rep = find_learning(rep_loc, rep_entry.id)
        if fresh_rep is None:
            raise ValueError(
                f"representative entry {rep_entry.id!r} in skill {rep_skill!r} no longer exists — "
                "this candidate is stale (likely already enacted by a concurrent `promote_cluster` "
                "call, or removed/revised meanwhile); re-run `compact --all` for a fresh finding"
            )

        global_id = write_global_entry(g_loc, backend, fresh_rep, rep_skill)
        retired = []
        for member_skill, entry in cluster:
            skill_loc = store_location(member_skill, config)
            with store_write_lock(skill_loc):
                index.rebuild_index_if_stale(skill_loc, backend)
                if find_learning(skill_loc, entry.id) is None:
                    continue  # already retired by the same race — nothing left to do here
                retire_source(skill_loc, backend, entry.id)
            retired.append({"skill": member_skill, "id": entry.id})

    return {
        "global_id": global_id,
        "representative": {"skill": rep_skill, "id": rep_entry.id},
        "skills": sorted({s for s, _ in cluster}),
        "retired": retired,
    }
