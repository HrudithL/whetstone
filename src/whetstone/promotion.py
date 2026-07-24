"""Promoting a preference into the learned global layer (§M5e).

A learning or issue that has proven itself *across skills* (or that a user lifts deliberately) is
moved out of its per-skill store into the reserved ``__global__`` store, where ``recall`` consults
it for every skill. This module is the **writer** half of the global layer:

- :func:`promote_to_global` — lift ONE entry from a skill store (manual ``whetstone promote``).
- :func:`write_global_entry` / :func:`retire_source` — the building blocks ``compact --all`` uses to
  promote a *cross-skill cluster* once and retire the redundant per-skill copies (M5a).

Ids are **always re-minted** in the global store — a foreign per-skill id is never trusted (the same
no-reuse discipline the rest of the store keeps). Two stores are mutated (global + the source
skill); both write locks are taken in a fixed order (global first, then the skill) so concurrent
promotions can never deadlock.
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
