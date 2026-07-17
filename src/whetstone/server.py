"""The Whetstone MCP server.

Milestone M1 adds the in-loop pair to M0's ``attach``: ``recall`` (embedding scope retrieval over
the markdown store) and ``capture`` (distill feedback into a scoped, deduped, committed entry).
Milestone M2a adds the measurement layer: recall/capture append to ``events.jsonl`` and the
out-of-band ``metrics`` tool reports the §11 KPIs. The still-to-come ``revise`` tool lands in M2b.
``main()`` runs the server over stdio.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import asdict
from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .embeddings import cosine, get_backend
from .metrics import compute_metrics
from .retrieval import retrieve
from .store import index
from .store.access import (
    next_id,
    reinforce_learning,
    save_issue,
    save_learning,
)
from .store.entries import IssueEntry, LearningEntry
from .store.index import IndexedEntry, entry_text
from .store.layout import (
    attach_skill,
    commit_store,
    ensure_store,
    read_registry,
    store_location,
    store_write_lock,
)
from .telemetry import emit_capture, emit_recall

mcp = FastMCP("whetstone")

# Exact §5.2 wording shipped to the model on every recall.
_HOW_TO_USE = (
    "Learnings have a 0–1 weight = how firmly to apply. Issues have NO weight — every "
    "issue returned is MANDATORY and must be handled before you complete, regardless of anything "
    "else."
)
_CAPTURE_CONTRACT = (
    "When the user reviews this output and asks for a change, the moment you implement that change "
    "also record it: `capture` for something new, `revise` for something already listed above (use "
    "its id). Pass this `run_id` on that `capture`/`revise` so the correction joins this run. A "
    "preference → a learning; a mistake or an 'always/never' rule → an issue."
)

_MAX_TITLE = 60


@mcp.tool()
def attach(skill: str, path: str | None = None) -> dict:
    """Register a skill so Whetstone tracks its learned layer.

    Optional setup: scaffolds a git-tracked, scope-organized store for ``skill`` and records it in
    the registry. Idempotent — attaching an already-attached skill is a no-op that reports
    ``already_attached``. ``recall``/``capture`` create a store lazily if you skip this. ``path`` is
    an optional reference to the target skill's location, recorded as provenance.

    Returns a summary: ``skill``, ``slug``, ``path`` (store dir), ``created`` (bool), ``status``.
    """
    return attach_skill(skill, skill_path=path)


@mcp.tool()
def recall(skill: str, intent: str, learnings_k: int | None = None) -> dict:
    """Call at the START of any task that might use an attached skill — call it blindly; empty is
    fine.

    Pass ``intent`` as a concrete, ELABORATED description of what you are about to produce,
    expanding vague requests into their specific dimensions (e.g. 'styling a table: color palette,
    number formatting, column alignment, row banding, density') — do NOT pass the user's raw words.
    This is the linchpin of retrieval quality (§5.4): "make a table styled well" embeds nowhere near
    a scope named 'currency formatting', but the elaborated dimensions do. No threshold fixes the
    abstraction gap; fixing the query does.

    Returns learnings (preferences, each with a 0-1 ``weight``) and issues (mandatory constraints,
    unweighted), plus ``how_to_use`` and a ``capture_contract`` you must honor, and a ``run_id`` to
    pass back on any follow-up ``capture``. An empty/unlearned store returns empty lists — never an
    error. ``learnings_k`` caps the number of (MMR-diversified) learnings returned; leave it unset
    to use the configured default (``learnings_k`` in config / ``WHETSTONE_LEARNINGS_K``).
    """
    config = load_config()
    ensure_store(skill, config)
    loc = store_location(skill, config)
    backend = get_backend(config)
    index.ensure_index(loc, backend)

    learnings, issues = retrieve(loc, intent, backend, config, learnings_k)
    run_id = _new_run_id()
    # Append the per-run event (§5.2, §11): the ids returned are the only per-run denominator for
    # application-rate metrics, since a run the user simply accepts produces no follow-up capture.
    emit_recall(loc, run_id, intent, [x.id for x in learnings], [x.id for x in issues])
    return {
        "skill": skill,
        "run_id": run_id,
        "learnings": [asdict(x) for x in learnings],
        "issues": [asdict(x) for x in issues],
        "how_to_use": _HOW_TO_USE,
        "capture_contract": _CAPTURE_CONTRACT,
    }


@mcp.tool()
def capture(
    skill: str,
    polarity: str,
    body: str,
    scope: str,
    provenance: str,
    run_id: str | None = None,
    confirm: bool = False,
) -> dict:
    """Call the moment you act on user feedback about output from an attached skill, when it's
    something *new*.

    Cues: a fix ('right-align that'), a preference ('I like muted palettes'), a rejection ('no, not
    like that'), approval of a specific choice. Classify: taste/preference →
    ``polarity:"learning"``; a mistake to never repeat, or an explicit 'always/never' rule →
    ``polarity:"issue"`` (word the body objectively). Generalize into a scoped rule of a few short
    sentences capturing the user's *why*; ``scope`` is a short phrase for when it applies ('currency
    columns'). Pass the ``run_id``
    from ``recall`` when this follows a recalled run. If it concerns something ``recall`` already
    listed, use ``revise`` instead (M2).

    Distills, then in code dedups: a near-duplicate learning is reinforced (``recurrence`` +1,
    refresh ``last_seen``) → ``reinforced``; a near-duplicate issue is a ``noop`` (issues have no
    recurrence); otherwise a new entry is written, indexed, and committed → ``committed``.
    """
    if polarity not in ("learning", "issue"):
        raise ValueError(f"polarity must be 'learning' or 'issue', got {polarity!r}")

    title = _title_from_body(body)

    config = load_config()
    ensure_store(skill, config)
    loc = store_location(skill, config)
    backend = get_backend(config)

    # The whole critical section runs under the per-store write lock so concurrent captures for the
    # same skill can't race on next_id (duplicate ids / lost entries) or interleave index rebuilds.
    # rebuild_index_if_stale is the lock-free variant (we already hold the lock here).
    with store_write_lock(loc):
        index.rebuild_index_if_stale(loc, backend)

        candidate_vec = backend.embed([entry_text(title, body)])[0]
        scope_vec = backend.embed([scope])[0]
        duplicate = _find_duplicate(loc, polarity, scope, candidate_vec, scope_vec, config)

        if polarity == "learning":
            if duplicate is not None:
                updated = reinforce_learning(loc, duplicate.id, when=_today())
                index.rebuild_index(loc, backend)
                commit_store(
                    loc, f"capture: reinforce {updated.id} (recurrence {updated.recurrence})"
                )
                emit_capture(loc, run_id, updated.id, polarity, "reinforced")
                return {
                    "status": "reinforced",
                    "entry_id": updated.id,
                    "recurrence": updated.recurrence,
                }
            entry_id = next_id(loc, "learning")
            today = _today()
            save_learning(
                loc,
                LearningEntry(
                    id=entry_id,
                    title=title,
                    body=body.strip(),
                    scope=scope,
                    provenance=provenance,
                    recurrence=1,
                    first_seen=today,
                    last_seen=today,
                ),
            )
            index.rebuild_index(loc, backend)
            commit_store(loc, f"capture: add {entry_id} ({scope})")
            emit_capture(loc, run_id, entry_id, polarity, "committed")
            return {"status": "committed", "entry_id": entry_id, "recurrence": 1}

        # polarity == "issue"
        if duplicate is not None:
            emit_capture(loc, run_id, duplicate.id, polarity, "noop")
            return {"status": "noop", "entry_id": duplicate.id}
        entry_id = next_id(loc, "issue")
        save_issue(
            loc,
            IssueEntry(
                id=entry_id,
                title=title,
                body=body.strip(),
                scope=scope,
                provenance=provenance,
            ),
        )
        index.rebuild_index(loc, backend)
        commit_store(loc, f"capture: add {entry_id} ({scope})")
        emit_capture(loc, run_id, entry_id, polarity, "committed")
        return {"status": "committed", "entry_id": entry_id, "recurrence": None}


@mcp.tool()
def metrics(skill: str | None = None) -> dict:
    """Reporting only — never call during normal work.

    Computes the §11 KPIs for the dashboard from each store's ``events.jsonl`` and current state:
    runs, average learnings-applied-per-run, capture counts by status, a repeat-correction proxy
    (reinforcement rate — the "money metric"), and %-survived. KPIs that need a known denominator or
    a labeled/calibration set — capture-rate, regressions-prevented, retrieval-precision — are
    returned as ``{"value": null, "note": ...}`` (they are computed only by the M3 showcase harness,
    never faked).

    Pass ``skill`` for one skill's report; omit it to report every attached skill under ``skills``.
    """
    config = load_config()
    if skill is not None:
        loc = store_location(skill, config)
        return {"skill": skill, **compute_metrics(loc)}
    return {
        "skills": {
            name: compute_metrics(store_location(name, config))
            for name in sorted(read_registry(config))
        }
    }


# --------------------------------------------------------------------------- helpers


def _today():
    return datetime.now(UTC).date()


def _new_run_id() -> str:
    return f"r-{_today().isoformat()}-{secrets.token_hex(2)}"


def _title_from_body(body: str) -> str:
    """A short single-line title for the markdown heading, distilled from the body's first sentence.

    ``capture`` takes no explicit title (§5.2), so one is derived. It is display metadata only — the
    body is the source of truth and is embedded/stored verbatim.
    """
    collapsed = " ".join(body.split())
    if not collapsed:
        raise ValueError("capture requires a non-empty body")
    first_sentence = re.split(r"(?<=[.!?])\s", collapsed, maxsplit=1)[0]
    return (first_sentence[:_MAX_TITLE].strip() or collapsed[:_MAX_TITLE].strip())


def _find_duplicate(
    loc,
    polarity: str,
    scope: str,
    candidate_vec: list[float],
    scope_vec: list[float],
    config,
) -> IndexedEntry | None:
    """The nearest same-polarity entry in the same/close scope, if it clears ``dedup_similarity``.

    "Close" means the other entry's scope-phrase is itself within ``dedup_similarity`` of the
    candidate's scope, so a near-identical body filed under an unrelated scope is not treated as a
    duplicate (§7).
    """
    scope_phrase = {s.scope: s.phrase for s in index.load_scopes(loc, polarity)}
    best: IndexedEntry | None = None
    best_sim = config.dedup_similarity
    for entry in index.load_entries(loc, polarity):
        if entry.scope != scope:
            phrase = scope_phrase.get(entry.scope)
            if phrase is None or cosine(scope_vec, phrase) < config.dedup_similarity:
                continue
        sim = cosine(candidate_vec, entry.vector)
        if sim >= best_sim:
            best_sim = sim
            best = entry
    return best


def main() -> None:
    """Console entry point: run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
