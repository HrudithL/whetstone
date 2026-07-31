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

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import replace

from .config import Config, load_config
from .embeddings import EmbeddingBackend, get_backend
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
    read_registry,
    registry_write_lock,
    store_location,
    store_write_lock,
)
from .telemetry import emit_promote


@contextmanager
def _both_locks(g_loc: StoreLocation, skill_loc: StoreLocation) -> Iterator[None]:
    """Hold the global and skill write locks in a fixed (global-first) order to avoid deadlock."""
    with store_write_lock(g_loc), store_write_lock(skill_loc):
        yield


def write_global_entry(
    g_loc: StoreLocation,
    backend: EmbeddingBackend,
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


def retire_source(skill_loc: StoreLocation, backend: EmbeddingBackend, entry_id: str) -> None:
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


def _find_cluster_for(
    clusters: list[list[tuple[str, LearningEntry]]], skill: str, entry_id: str
) -> list[tuple[str, LearningEntry]] | None:
    """The cluster (if any) containing the given ``(skill, entry_id)`` pair."""
    return next((c for c in clusters if any(s == skill and e.id == entry_id for s, e in c)), None)


def promote_cluster(skill: str, entry_id: str, config: Config | None = None) -> dict:
    """Enact one cross-skill promotion candidate reported by ``compact --all`` (§M7a).

    ``skill``/``entry_id`` must name the cluster's *current representative* — the same one a
    ``global_candidate`` finding's ``representative`` field names, and the same deterministic pick
    :func:`whetstone.compaction.cluster_representative` makes. Passing a non-representative member
    (or a stale representative that a concurrent reinforcement has since replaced) is rejected
    rather than silently substituted, so the write always uses the exact entry the caller named.
    Re-runs the same cross-skill clustering detection, restricted to whichever cluster contains
    that entry, then performs the write ``compact --all`` used to do automatically: the
    representative is written into the global store and every cluster member — across all its
    skills — is retired from its per-skill store. This is the only place a cross-skill cluster is
    actually promoted; ``compact --all`` itself only ever detects and reports.

    Detection runs twice: once unlocked (to fail fast on an obviously-stale candidate before
    bothering to take any lock), and again over **every currently-registered skill, with the
    registry itself held frozen** (nested inside the global lock, in sorted order — see below) —
    only the **second, fully-locked** run is ever acted on. This matters for four independent
    reasons: (1) the global lock alone only serializes *other* ``promote_cluster`` calls, not
    `capture`/`revise`/`compact <skill>`, which each only take their own source store's lock — so
    every store that could possibly join or leave the cluster must be locked too, before the final
    check, or one of those could mutate a member out from under this call between detection and the
    write; (2) detection re-checks real cluster membership — same-skill dedup-similarity threshold
    *and* ``global_skill_count`` — not just whether an id still exists, so a member that was revised
    (not removed), or a cluster that dropped below threshold, is caught the same way an
    outright-removed entry is; (3) the registry is frozen (below) for this call's whole write+retire
    span, not just read once — locking every skill *that exists right now* isn't enough on its own,
    because a brand-new skill could finish registering, with a matching learning already captured,
    at any point between that snapshot and the retirement loop completing; that new copy would never
    get locked or retired, and — critically — a later ``compact --all`` can NOT clean it up
    afterwards, because cross-skill clustering only ever compares PER-SKILL learnings against each
    other, never against an already-promoted GLOBAL entry, so a lone straggler left behind by this
    call has no automatic path back into the global layer (round-4 Codex review finding: this is
    stronger than "a later compact --all will catch it," which turns out to be false once the rest
    of the cluster has already been retired); (4) because the registry is frozen for the whole
    span (not just re-read repeatedly until it looks stable), a single read of it is authoritative —
    there is no separate "grow the lock set to a fixed point" loop to reason about.

    Freezing the registry: :func:`whetstone.store.layout.registry_write_lock` is the SAME lock
    :func:`whetstone.store.layout._register` must hold to add a skill — so while this call holds
    it, no new skill can finish registering, full stop. That makes one read of the registry, taken
    right after acquiring this lock, good for the rest of the call: locking, detection, and the
    writes below all operate on that one list, with no window for it to grow underneath them.

    Lock order is global-first, then the registry, then every registered skill in sorted order —
    the same global-then-skill convention :func:`promote_to_global` uses, with the registry lock
    slotted in between so two concurrent ``promote_cluster`` calls (or a concurrent `attach`) can
    never deadlock against each other or race on what "every registered skill" means.

    Raises ``ValueError`` if no current cluster containing ``(skill, entry_id)`` meets
    ``global_skill_count`` — the candidate may be stale (already enacted, revised, or removed since
    it was reported), the entry may not exist, or the passed entry is a cluster member but not (or
    no longer) its representative.
    """
    if config is None:
        config = load_config()
    if skill == GLOBAL_SLUG:
        raise ValueError("cannot promote from the global store to itself")

    # Lazy import: compaction.py imports from this module at load time, so importing it back at
    # module level here would create a circular import. Deferring to call time breaks the cycle.
    from .compaction import cluster_representative, find_cross_skill_clusters

    backend = get_backend(config)

    def _stale_error() -> ValueError:
        return ValueError(
            f"no cross-skill cluster containing {entry_id!r} in skill {skill!r} meets "
            f"global_skill_count={config.global_skill_count} right now — the candidate may be "
            "stale (already enacted, revised, or removed since it was reported); re-run "
            "`compact --all` for a fresh finding"
        )

    # Fail fast, unlocked — a cheap check before we bother taking any lock at all. This is
    # deliberately NOT used to scope which stores get locked below (see the docstring): a skill
    # this provisional scan misses entirely could still join the true cluster by the time the
    # authoritative, fully-locked scan runs.
    provisional = _find_cluster_for(find_cross_skill_clusters(config, backend), skill, entry_id)
    if provisional is None:
        raise _stale_error()

    ensure_store(GLOBAL_SLUG, config)
    g_loc = global_store_location(config)

    with store_write_lock(g_loc):
        index.rebuild_index_if_stale(g_loc, backend)

        # Freeze the registry for the rest of this call: `registry_write_lock` is the same lock
        # `_register` needs to add a skill, so while we hold it, no new skill can finish
        # registering — the registry cannot grow underneath us. That makes the read right below
        # authoritative for the whole span (detection AND the writes), not just the instant it's
        # taken, which is why no repeated-read "fixed point" loop is needed here (round-4 Codex
        # review finding on the previous approach: a snapshot-then-lock loop that settles still
        # leaves a gap for a fresh, independent read taken later to see something new — freezing the
        # registry itself removes that gap entirely rather than chasing it with more reads).
        with registry_write_lock(config), ExitStack() as stack:
            locked = sorted(read_registry(config))
            for reg_skill in locked:
                stack.enter_context(store_write_lock(store_location(reg_skill, config)))

            # The authoritative check, over exactly the frozen `locked` list above — never a fresh
            # `find_cross_skill_clusters(config, backend)` call, which would re-read the registry
            # itself (redundant and, without the freeze above, unsafe).
            cluster = _find_cluster_for(
                find_cross_skill_clusters(config, backend, skills=locked),
                skill,
                entry_id,
            )
            if cluster is None:
                raise _stale_error()

            rep_skill, rep_entry = cluster_representative(cluster)
            if (rep_skill, rep_entry.id) != (skill, entry_id):
                raise ValueError(
                    f"{entry_id!r} in skill {skill!r} is a cluster member but not its current "
                    f"representative (that's {rep_entry.id!r} in skill {rep_skill!r} now) — pass "
                    "the representative a `global_candidate` finding names, or re-run "
                    "`compact --all` for a fresh one"
                )

            global_id = write_global_entry(g_loc, backend, rep_entry, rep_skill)
            retired = []
            for member_skill, entry in cluster:
                member_loc = store_location(member_skill, config)
                retire_source(member_loc, backend, entry.id)
                retired.append({"skill": member_skill, "id": entry.id})

    return {
        "global_id": global_id,
        "representative": {"skill": rep_skill, "id": rep_entry.id},
        "skills": sorted({s for s, _ in cluster}),
        "retired": retired,
    }
