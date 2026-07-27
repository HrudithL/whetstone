"""The Whetstone MCP server.

Milestone M1 adds the in-loop pair to M0's ``attach``: ``recall`` (embedding scope retrieval over
the markdown store) and ``capture`` (distill feedback into a scoped, deduped, committed entry).
Milestone M2a adds the measurement layer: recall/capture append to ``events.jsonl`` and the
out-of-band ``metrics`` tool reports the §11 KPIs. Milestone M2b adds the confirmation-gated editing
layer: the ``revise`` tool (reinforce/weaken/remove/promote/demote), the supervision dial (§9)
applied in both ``capture`` and ``revise``, the promotion threshold (§6), and cross-polarity
conflict detection in ``capture`` (§7). ``main()`` runs the server over stdio.
"""

from __future__ import annotations

import json
import re
import secrets
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP

from .config import Config, load_config
from .embeddings import cosine, get_backend
from .metrics import compute_metrics
from .retrieval import RecalledIssue, RecalledLearning, RetrievalSnapshot, retrieve
from .store import index
from .store.access import (
    demote_issue_to_learning,
    find_issue,
    find_learning,
    next_id,
    promote_learning_to_issue,
    record_id,
    reinforce_learning,
    remove_entry,
    save_issue,
    save_learning,
    set_learning_recurrence,
    update_learning_prose,
)
from .store.entries import IssueEntry, LearningEntry
from .store.index import IndexedEntry, entry_text
from .store.layout import (
    GLOBAL_SLUG,
    StoreLocation,
    attach_skill,
    commit_store,
    ensure_store,
    global_store_location,
    is_store,
    read_registry,
    store_location,
    store_write_lock,
)
from .store.markdown import validate_body
from .store.slug import normalize_scope
from .telemetry import emit_capture, emit_recall, emit_revise

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
# revise statuses that represent a committed change worth announcing to the user (§M5d).
_REVISE_TERMINAL = {"reinforced", "revised", "removed", "promoted", "demoted"}


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

    Each entry carries an ``origin``: ``"skill"`` (this skill's own learned store) or ``"global"``
    (a preference that recurred across skills and was promoted to Whetstone's learned global layer,
    §M5e). Prefer a more specific ``"skill"`` entry when it conflicts with a broader ``"global"``
    one. The global layer can be disabled with ``consult_global=false`` in config.

    When you apply a returned learning/issue to your output, briefly NAME it to the user (e.g.
    "using your saved preference for muted palettes") so the learned layer is visible, not silent.

    ``conflicts`` (§M7b) flags pairs, within the entries just returned, where a learning affirms
    what a co-returned issue forbids — e.g. a "right-align currency" learning alongside a "never
    right-align currency" issue. Each item is ``{"a": <learning id>, "a_origin": ..., "a_skill":
    ..., "b": <issue id>, "b_origin": ..., "b_skill": ..., "note": ..}``. ``*_origin`` disambiguates
    ids since the skill and global stores mint ids independently and can collide; ``*_skill`` is the
    literal ``skill`` argument to pass to `revise` for that side — for a ``"global"``-origin entry
    this is the reserved global slug, NOT this call's own ``skill``, since `revise` always resolves
    ``entry_id`` against the store named by its ``skill`` argument. Always present (``[]`` when
    nothing conflicts). The issue always wins (§5.2) — resolve the tension in your output, and
    consider `revise`-ing the losing side: ``revise(skill=<its *_skill>, entry_id=<its id>, ...)``.
    """
    config = load_config()
    ensure_store(skill, config)
    loc = store_location(skill, config)
    backend = get_backend(config)
    index.ensure_index(loc, backend)

    # §M7b: `snapshot_out` captures the raw entries/scope vectors THIS retrieve() call reads, from
    # the same connection/snapshot, for the conflict pass below — never a separate whole-store scan
    # and never at risk of racing a concurrent capture/revise index rebuild after this call returns.
    snapshot = RetrievalSnapshot()
    learnings, issues = retrieve(loc, intent, backend, config, learnings_k, snapshot_out=snapshot)
    run_id = _new_run_id()
    # Append the per-run event (§5.2, §11): the ids returned are the only per-run denominator for
    # application-rate metrics, since a run the user simply accepts produces no follow-up capture.
    emit_recall(loc, run_id, intent, [x.id for x in learnings], [x.id for x in issues])

    # M5e — the learned global layer. Orchestration ONLY: run the SAME per-store retrieval over the
    # reserved `__global__` store and union the (origin-tagged) results. Retrieval logic is
    # untouched — global entries default to origin "skill" from `retrieve()`, re-stamped here.
    # `consult_global=false` (or recalling the global store itself) skips this, so the payload is
    # byte-identical to per-skill-only recall. recall never *creates* the global store — it only
    # consults it when a writer (promote / compact --all) has already populated it.
    g_loc = global_store_location(config)
    g_snapshot = RetrievalSnapshot()
    if config.consult_global and loc.slug != GLOBAL_SLUG and is_store(g_loc.path):
        index.ensure_index(g_loc, backend)
        g_learnings, g_issues = retrieve(
            g_loc, intent, backend, config, learnings_k, snapshot_out=g_snapshot
        )
        if g_learnings or g_issues:
            # Give the global store its own usage telemetry (its stale/harden mining reasons over
            # its own log), keyed to the same run_id so a follow-up capture can still be correlated.
            emit_recall(
                g_loc, run_id, intent, [x.id for x in g_learnings], [x.id for x in g_issues]
            )
        learnings = learnings + [replace(x, origin="global") for x in g_learnings]
        issues = issues + [replace(x, origin="global") for x in g_issues]

    # M7b — conflict visibility. Purely additive, read-only OBSERVER pass over the finalized
    # learnings/issues (after the skill/global union above): it never changes what was retrieved,
    # how it was ranked/capped (MMR), or the fallback floor (see the M5e comment above — retrieval
    # logic itself is never touched here either). It only annotates the payload already decided.
    conflicts = (
        _recall_conflicts(skill, snapshot, g_snapshot, learnings, issues, config)
        if learnings and issues
        else []
    )

    return {
        "skill": skill,
        "run_id": run_id,
        "learnings": [asdict(x) for x in learnings],
        "issues": [asdict(x) for x in issues],
        "how_to_use": _HOW_TO_USE,
        "capture_contract": _CAPTURE_CONTRACT,
        "conflicts": conflicts,
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
    recurrence); otherwise a new entry is written, indexed, and committed → ``committed``. A new
    entry that contradicts an existing opposite-polarity rule returns ``conflict`` (resolve it with
    ``revise``) instead of committing. In supervised mode a new/changed entry returns
    ``needs_confirmation`` first — re-call with ``confirm:true`` to commit. When a reinforcement
    pushes a learning to the promotion threshold (§6) the reinforcement is committed and
    ``needs_confirmation`` is returned; resolve the promotion via ``revise`` (the returned prompt
    tells you how) — ``capture`` never promotes.

    On a committed/reinforced result the payload carries a ``confirmation`` string (e.g. "Captured:
    <scope> — …. Re-applies on future <skill> runs."). RELAY it to the user so they can see the
    correction was recorded and will stick — the learned layer is otherwise invisible to them.
    """
    if polarity not in ("learning", "issue"):
        raise ValueError(f"polarity must be 'learning' or 'issue', got {polarity!r}")

    scope = normalize_scope(scope)  # same string for filename hash, stored scope, and embedding
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
                return _capture_reinforce(loc, backend, duplicate, run_id, confirm, config)
            conflict = _find_conflict(
                loc, "learning", scope, title, body, candidate_vec, scope_vec, config
            )
            if conflict is not None:
                return _conflict_result(loc, run_id, "learning", conflict)
            if _supervised_hold(config, confirm):
                return _needs_confirmation(
                    None,
                    f"Supervised mode: commit this new learning about {scope!r}? "
                    f"Re-call `capture` with confirm:true.",
                )
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
            record_id(loc, entry_id)
            index.rebuild_index(loc, backend)
            commit_store(loc, f"capture: add {entry_id} ({scope})")
            emit_capture(loc, run_id, entry_id, polarity, "committed", scope=scope)
            return {
                "status": "committed",
                "entry_id": entry_id,
                "recurrence": 1,
                "confirmation": _capture_confirmation(loc, scope, body, "committed"),
            }

        # polarity == "issue"
        # Cross-polarity conflict is checked BEFORE same-polarity dedup: a new prohibiting "Never X"
        # issue must surface its conflict with an existing "X" learning rather than be silently
        # nooped against a similar (aligned) "Always X" issue (§7).
        conflict = _find_conflict(
            loc, "issue", scope, title, body, candidate_vec, scope_vec, config
        )
        # Also detect a new issue contradicting an EXISTING issue (issue<->issue): same/close scope,
        # high similarity, opposite prohibition-polarity (new `Never X` vs existing `Always X`).
        if conflict is None:
            conflict = _find_issue_conflict(
                loc, scope, title, body, candidate_vec, scope_vec, config
            )
        if conflict is not None:
            return _conflict_result(loc, run_id, "issue", conflict)
        if duplicate is not None:
            emit_capture(loc, run_id, duplicate.id, polarity, "noop", scope=duplicate.scope)
            return {
                "status": "noop",
                "entry_id": duplicate.id,
                "confirmation": _capture_confirmation(loc, duplicate.scope, duplicate.body, "noop"),
            }
        if _supervised_hold(config, confirm):
            return _needs_confirmation(
                None,
                f"Supervised mode: commit this new issue about {scope!r}? "
                f"Re-call `capture` with confirm:true.",
            )
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
        record_id(loc, entry_id)
        index.rebuild_index(loc, backend)
        commit_store(loc, f"capture: add {entry_id} ({scope})")
        emit_capture(loc, run_id, entry_id, polarity, "committed", scope=scope)
        return {
            "status": "committed",
            "entry_id": entry_id,
            "recurrence": None,
            "confirmation": _capture_confirmation(loc, scope, body, "committed"),
        }


def _capture_reinforce(
    loc: StoreLocation,
    backend,
    duplicate: IndexedEntry,
    run_id: str | None,
    confirm: bool,
    config: Config,
) -> dict:
    """The dedup-reinforce path of ``capture``: bump recurrence, honoring the supervision dial and
    surfacing the promotion threshold (§6).

    Promotion is NOT executed here — that lives solely in ``revise`` (single source of truth). At
    the threshold the reinforcement is still committed and a ``needs_confirmation`` is returned
    pointing the caller at ``revise(action="promote", ...)``, so the promotion runs against the
    entry's id, never a reworded body re-run through dedup (which could fall below the cutoff and
    mis-create a fresh learning)."""
    if _supervised_hold(config, confirm):
        return _needs_confirmation(
            duplicate.id,
            f"Supervised mode: reinforce {duplicate.id} "
            f"(recurrence {duplicate.recurrence} -> {duplicate.recurrence + 1})? "
            f"Re-call `capture` with confirm:true.",
        )
    updated = reinforce_learning(loc, duplicate.id, when=_today())
    index.rebuild_index(loc, backend)
    commit_store(loc, f"capture: reinforce {updated.id} (recurrence {updated.recurrence})")
    emit_capture(loc, run_id, updated.id, "learning", "reinforced", scope=updated.scope)
    if updated.recurrence >= config.promotion_threshold:
        return {
            "status": "needs_confirmation",
            "entry_id": updated.id,
            "recurrence": updated.recurrence,
            "prompt": _capture_promote_prompt(updated.id, updated.recurrence),
        }
    return {
        "status": "reinforced",
        "entry_id": updated.id,
        "recurrence": updated.recurrence,
        "confirmation": _capture_confirmation(loc, updated.scope, updated.body, "reinforced"),
    }


@mcp.tool()
def revise(
    skill: str,
    entry_id: str,
    action: str,
    body: str | None = None,
    scope: str | None = None,
    run_id: str | None = None,
    confirm: bool | str = False,
) -> dict:
    """Call when user feedback concerns a learning or issue that ``recall`` already showed you (use
    its ``id``).

    ``action`` ∈ ``reinforce`` (they repeated a preference), ``weaken`` (they contradicted one),
    ``promote`` (a preference should become an always/never rule), ``demote`` (a hard rule should
    soften to a preference), ``remove`` (they rejected it outright). Optional ``body``/``scope``
    supply reworded prose — REQUIRED for ``promote`` (reword the subjective preference into an
    objective 'Always …'/'Never …' rule), usable to reword the survivor in conflict resolution.

    If the server returns ``needs_confirmation``, ask the user the returned ``prompt``, then re-call
    with ``confirm`` set to their choice:
    - ``reinforce`` reaching the promotion threshold (§6) → ``confirm:"promote"`` or ``"keep"``.
    - ``weaken`` taking a learning below recurrence 0 → ``confirm:"keep"`` or ``"remove"``.
    - ``promote`` always asks first → re-call with ``confirm:true`` (and ``body``).
    - ``weaken``/``remove`` on an *issue* is a 3-way hard-rule prompt → ``confirm:"remove"``,
      ``"demote"``, or ``"cancel"``.
    - In supervised mode every routine mutation asks first → re-call with ``confirm:true``.

    On a committed change the payload carries a ``confirmation`` string — RELAY it to the user so
    the (otherwise invisible) update to the learned layer is visible.
    """
    if action not in ("reinforce", "weaken", "remove", "promote", "demote"):
        raise ValueError(
            "action must be one of reinforce|weaken|remove|promote|demote, "
            f"got {action!r}"
        )
    if scope is not None:
        scope = normalize_scope(scope)  # keep reworded scope consistent with filename + storage
    config = load_config()
    ensure_store(skill, config)
    loc = store_location(skill, config)
    backend = get_backend(config)

    # One critical section per revise (mirrors capture): duplicate/id allocation, markdown write,
    # index rebuild, and git commit are serialized against concurrent mutations of the same store.
    with store_write_lock(loc):
        index.rebuild_index_if_stale(loc, backend)
        if action == "reinforce":
            result = _revise_reinforce(loc, backend, entry_id, body, scope, run_id, confirm, config)
        elif action == "weaken":
            result = _revise_weaken(loc, backend, entry_id, body, scope, run_id, confirm, config)
        elif action == "remove":
            result = _revise_remove(loc, backend, entry_id, body, scope, run_id, confirm, config)
        elif action == "promote":
            result = _revise_promote(loc, backend, entry_id, body, scope, run_id, confirm, config)
        else:
            result = _revise_demote(loc, backend, entry_id, body, scope, run_id, confirm, config)
    # Attach a human-facing confirmation on a terminal change so the agent can relay it (§M5d).
    # A `needs_confirmation`/`unchanged` result gets none — nothing was committed to announce.
    if result.get("status") in _REVISE_TERMINAL and result.get("entry_id"):
        result = {
            **result,
            "confirmation": _revise_confirmation(loc, result["entry_id"], action, result["status"]),
        }
    return result


def _revise_reinforce(loc, backend, entry_id, body, scope, run_id, confirm, config) -> dict:
    """``reinforce``: recurrence +1, refresh ``last_seen``; prompt at the promotion threshold (§6).

    ``confirm:"promote"``/``"keep"`` answer a prior threshold prompt (the +1 already committed), so
    they resolve the promotion without bumping again."""
    if confirm == "promote":
        current = find_learning(loc, entry_id)
        if current is None:
            _reject_missing_learning(loc, entry_id, "promote")
        # Only honor a "promote" answer when a threshold prompt was actually pending (recurrence has
        # reached the threshold). Otherwise `revise(action="reinforce", confirm="promote")` on a
        # low-recurrence learning would bypass promote's always-confirm; fall through to a normal
        # reinforce instead (an explicit promotion must use `action="promote"`).
        if current.recurrence >= config.promotion_threshold:
            return _promote_or_ask_body(loc, backend, entry_id, body, scope, run_id)
    elif confirm == "keep":
        current = find_learning(loc, entry_id)
        if current is None:
            _reject_missing_learning(loc, entry_id, "reinforce")
        # Only treat "keep" as the answer to a pending promotion prompt (recurrence has reached the
        # threshold, so the +1 already happened on that call). Below the threshold there was no
        # prompt, so this is an out-of-context keep — fall through to an actual reinforcement rather
        # than reporting a phantom "reinforced" that never bumped/committed.
        if current.recurrence >= config.promotion_threshold:
            return {
                "status": "reinforced",
                "entry_id": current.id,
                "recurrence": current.recurrence,
            }

    learning = find_learning(loc, entry_id)
    if learning is None:
        _reject_missing_learning(loc, entry_id, "reinforce")
    if _supervised_hold(config, confirm):
        return _needs_confirmation(
            entry_id, f"Supervised mode: reinforce {entry_id}? Re-call `revise` with confirm:true."
        )
    # Build + VALIDATE any reworded prose before the recurrence bump, so an invalid body fails
    # cleanly with no partial mutation (the bump/scope-move would otherwise already be on disk).
    prose = _prepare_prose(entry_id, learning, body, scope)
    updated = reinforce_learning(loc, entry_id, when=_today())
    # A corrected wording supplied alongside the reinforcement updates the stored prose (and, on the
    # index rebuild below, its embedding) so markdown never keeps stale text (§5.2).
    if prose is not None:
        updated = update_learning_prose(loc, entry_id, **prose)
    index.rebuild_index(loc, backend)
    commit_store(loc, f"revise: reinforce {updated.id} (recurrence {updated.recurrence})")
    emit_revise(loc, run_id, updated.id, "reinforce", "reinforced", scope=updated.scope)
    if updated.recurrence >= config.promotion_threshold:
        return {
            "status": "needs_confirmation",
            "entry_id": updated.id,
            "recurrence": updated.recurrence,
            "prompt": _promote_prompt(updated.recurrence),
        }
    return {"status": "reinforced", "entry_id": updated.id, "recurrence": updated.recurrence}


def _revise_weaken(loc, backend, entry_id, body, scope, run_id, confirm, config) -> dict:
    """``weaken``: recurrence −1. Below 0 prompts keep/remove; on an *issue* it's the 3-way
    hard-rule prompt."""
    learning = find_learning(loc, entry_id)
    if learning is None:
        if find_issue(loc, entry_id) is not None:
            return _issue_contradiction(
                loc, backend, entry_id, body, scope, run_id, confirm, config
            )
        raise ValueError(f"no entry with id {entry_id!r}")

    # Answers to a prior below-0 prompt. Guard against a STALE answer: the prompt was issued at the
    # bottom (recurrence 0). If a concurrent call reinforced the learning since (recurrence > 0),
    # the user is answering about a learning that has since been reinstated — do not delete/reset
    # it; report the current state and let the caller re-issue.
    if confirm in ("keep", "remove"):
        if learning.recurrence > 0:
            return {"status": "unchanged", "entry_id": entry_id, "recurrence": learning.recurrence}
    if confirm == "keep":
        # A conflict-resolution "keep with rewording" updates the prose too; validate up front.
        prose = _prepare_prose(entry_id, learning, body, scope)
        set_learning_recurrence(loc, entry_id, 1)
        if prose is not None:
            update_learning_prose(loc, entry_id, **prose)
        index.rebuild_index(loc, backend)
        commit_store(loc, f"revise: keep {entry_id} (recurrence 1)")
        emit_revise(loc, run_id, entry_id, "weaken", "revised", scope=learning.scope)
        return {"status": "revised", "entry_id": entry_id, "recurrence": 1}
    if confirm == "remove":
        remove_entry(loc, entry_id)
        index.rebuild_index(loc, backend)
        commit_store(loc, f"revise: remove {entry_id}")
        emit_revise(loc, run_id, entry_id, "weaken", "removed", scope=learning.scope)
        return {"status": "removed", "entry_id": entry_id}

    new_recurrence = learning.recurrence - 1
    if new_recurrence < 0:
        return {
            "status": "needs_confirmation",
            "entry_id": entry_id,
            "recurrence": learning.recurrence,
            "prompt": (
                "You've gone against this learning — keep it (reset to recurrence 1) or remove it? "
                "Re-call `revise` with confirm:'keep' or confirm:'remove'."
            ),
        }
    if _supervised_hold(config, confirm):
        return _needs_confirmation(
            entry_id,
            f"Supervised mode: weaken {entry_id} "
            f"(recurrence {learning.recurrence} -> {new_recurrence})? "
            f"Re-call `revise` with confirm:true.",
        )
    # Conflict resolution can reword the surviving (weakened) entry. Build + VALIDATE up front so an
    # invalid body fails cleanly before the recurrence change / scope move (§7).
    prose = _prepare_prose(entry_id, learning, body, scope)
    set_learning_recurrence(loc, entry_id, new_recurrence)
    if prose is not None:
        update_learning_prose(loc, entry_id, **prose)
    index.rebuild_index(loc, backend)
    commit_store(loc, f"revise: weaken {entry_id} (recurrence {new_recurrence})")
    emit_revise(loc, run_id, entry_id, "weaken", "revised", scope=learning.scope)
    return {"status": "revised", "entry_id": entry_id, "recurrence": new_recurrence}


def _revise_remove(loc, backend, entry_id, body, scope, run_id, confirm, config) -> dict:
    """``remove``: delete a learning (dial-governed) or route an issue through the hard-rule
    3-way prompt."""
    learning = find_learning(loc, entry_id)
    if learning is not None:
        if _supervised_hold(config, confirm):
            return _needs_confirmation(
                entry_id,
                f"Supervised mode: remove learning {entry_id}? Re-call `revise` with confirm:true.",
            )
        remove_entry(loc, entry_id)
        index.rebuild_index(loc, backend)
        commit_store(loc, f"revise: remove {entry_id}")
        emit_revise(loc, run_id, entry_id, "remove", "removed", scope=learning.scope)
        return {"status": "removed", "entry_id": entry_id}
    if find_issue(loc, entry_id) is not None:
        return _issue_contradiction(loc, backend, entry_id, body, scope, run_id, confirm, config)
    raise ValueError(f"no entry with id {entry_id!r}")


def _revise_promote(loc, backend, entry_id, body, scope, run_id, confirm, config) -> dict:
    """``promote`` (learning → issue): ALWAYS prompts first (§6), regardless of supervision mode.

    Only an explicit yes promotes: ``confirm in (True, "promote")``. A declined prompt
    (``confirm in ("keep", "cancel")``) leaves the entry a learning and returns ``unchanged`` — a
    non-empty confirm string must never be read as blanket assent."""
    learning = find_learning(loc, entry_id)
    if learning is None:
        _reject_missing_learning(loc, entry_id, "promote")
    if confirm in (True, "promote"):
        return _promote_or_ask_body(loc, backend, entry_id, body, scope, run_id)
    if _confirmed(confirm):  # a declining answer (e.g. "keep"/"cancel") — do not promote
        return {"status": "unchanged", "entry_id": entry_id, "recurrence": learning.recurrence}
    return {
        "status": "needs_confirmation",
        "entry_id": entry_id,
        "recurrence": learning.recurrence,
        "prompt": _promote_prompt(learning.recurrence),
    }


def _revise_demote(loc, backend, entry_id, body, scope, run_id, confirm, config) -> dict:
    """``demote`` (issue → learning): seed recurrence and dates; dial-governed."""
    issue = find_issue(loc, entry_id)
    if issue is None:
        if find_learning(loc, entry_id) is not None:
            raise ValueError(f"demote applies to issues; {entry_id!r} is a learning")
        raise ValueError(f"no issue with id {entry_id!r}")
    if _supervised_hold(config, confirm):
        return _needs_confirmation(
            entry_id,
            f"Supervised mode: soften issue {entry_id} to a learning? "
            f"Re-call `revise` with confirm:true.",
        )
    return _do_demote(loc, backend, entry_id, body, scope, run_id, config)


def _issue_contradiction(loc, backend, entry_id, body, scope, run_id, confirm, config) -> dict:
    """The 3-way hard-rule prompt for ``weaken``/``remove`` on an issue — ALWAYS asks (§6),
    regardless of supervision mode: remove it, demote it to a preference, or cancel."""
    if confirm == "remove":
        removed_issue = find_issue(loc, entry_id)
        remove_entry(loc, entry_id)
        index.rebuild_index(loc, backend)
        commit_store(loc, f"revise: remove issue {entry_id}")
        emit_revise(
            loc,
            run_id,
            entry_id,
            "remove",
            "removed",
            scope=removed_issue.scope if removed_issue else None,
        )
        return {"status": "removed", "entry_id": entry_id}
    if confirm == "demote":
        return _do_demote(loc, backend, entry_id, body, scope, run_id, config)
    if confirm == "cancel":
        return {"status": "unchanged", "entry_id": entry_id}
    return {
        "status": "needs_confirmation",
        "entry_id": entry_id,
        "prompt": (
            "This was made a hard rule (issue) and you're going against it — fully remove it, "
            "soften it to a preference, or make no change? Re-call `revise` with confirm:'remove', "
            "confirm:'demote', or confirm:'cancel'."
        ),
    }


def _do_demote(loc, backend, entry_id, body, scope, run_id, config) -> dict:
    """Move an issue to ``learnings/`` seeded at ``demote_seed_recurrence`` with today's dates."""
    new_id = next_id(loc, "learning")
    learning = demote_issue_to_learning(
        loc,
        entry_id,
        new_id,
        seed_recurrence=config.demote_seed_recurrence,
        when=_today(),
        body=body,
        scope=scope,
    )
    record_id(loc, learning.id)
    index.rebuild_index(loc, backend)
    commit_store(loc, f"revise: demote issue {entry_id} -> {learning.id}")
    emit_revise(loc, run_id, learning.id, "demote", "demoted", scope=learning.scope)
    return {"status": "demoted", "entry_id": learning.id, "recurrence": learning.recurrence}


def _promote_or_ask_body(loc, backend, entry_id, body, scope, run_id) -> dict:
    """Execute a promotion, or ask for the objective rewording when ``body`` is missing (§6)."""
    if not (body and body.strip()):
        return _needs_confirmation(
            entry_id,
            "Promotion needs an objective rewording — re-call "
            f"`revise(entry_id={entry_id!r}, action='promote', confirm='promote', body=…)` with "
            "`body` phrased as an 'Always …' / 'Never …' rule.",
        )
    new_id = next_id(loc, "issue")
    issue = promote_learning_to_issue(loc, entry_id, new_id, body=body, scope=scope)
    record_id(loc, issue.id)
    index.rebuild_index(loc, backend)
    commit_store(loc, f"revise: promote {entry_id} -> {issue.id}")
    emit_revise(loc, run_id, issue.id, "promote", "promoted", scope=issue.scope)
    return {"status": "promoted", "entry_id": issue.id}


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
    return f"r-{_today().isoformat()}-{secrets.token_hex(8)}"


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


def _prepare_prose(
    entry_id: str, current: LearningEntry, body: str | None, scope: str | None
) -> dict | None:
    """Build the reworded ``{title, body, scope}`` for a learning, or None if none was supplied.

    Validates the new body up front (raising :class:`MarkdownParseError` BEFORE any caller mutates
    the store), so a body that would corrupt the store fails cleanly with no partial write. The
    returned dict is spread straight into :func:`update_learning_prose`.
    """
    has_body = bool(body and body.strip())
    if not has_body and not scope:
        return None
    new_body = body.strip() if has_body else current.body
    new_scope = scope if scope else current.scope
    new_title = _title_from_body(new_body) if has_body else current.title
    validate_body(entry_id, new_body)
    return {"title": new_title, "body": new_body, "scope": new_scope}


def _confirmed(confirm: bool | str) -> bool:
    """Whether ``confirm`` carries the user's assent — ``True`` or any non-empty choice string."""
    if isinstance(confirm, bool):
        return confirm
    return bool(str(confirm).strip())


def _supervised_hold(config: Config, confirm: bool | str) -> bool:
    """Whether the supervision dial (§9) must gate this routine change before it commits.

    Only ``supervised`` mode holds; ``balanced``/``autonomous`` commit routine changes silently.
    Approval must be EXPLICIT: only the boolean ``True`` releases the hold. A non-empty confirm
    string (e.g. ``"cancel"``/``"no"``) is NOT assent — any prompt-specific accepted choice is
    recognized by the calling branch before it reaches this gate, so here anything other than
    ``True`` keeps the hold. Promotion and issue-contradiction removals prompt independently (§6).
    """
    return config.supervision == "supervised" and confirm is not True


def _needs_confirmation(entry_id: str | None, prompt: str) -> dict:
    return {"status": "needs_confirmation", "entry_id": entry_id, "prompt": prompt}


def _one_line(body: str, limit: int = 80) -> str:
    """A single-line, length-bounded gist of ``body`` for a human-facing confirmation string."""
    collapsed = " ".join(body.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1].rstrip() + "…"


def _capture_confirmation(loc: StoreLocation, scope: str, body: str, status: str) -> str:
    """The concise, human-facing line ``capture`` returns so the agent can relay what it recorded
    (§M5d — visibility without a query tool)."""
    verb = {"committed": "Captured", "reinforced": "Reinforced", "noop": "Already knew"}[status]
    return f"{verb}: {scope} — {_one_line(body)}. Re-applies on future {loc.skill} runs."


def _revise_confirmation(loc: StoreLocation, entry_id: str, action: str, status: str) -> str:
    """The concise, human-facing line ``revise`` returns so the agent can relay it (§M5d)."""
    verb = {
        "reinforced": "Reinforced",
        "revised": "Updated",
        "removed": "Removed",
        "promoted": "Promoted to a mandatory issue",
        "demoted": "Softened to a preference",
    }.get(status, status.capitalize())
    return f"{verb} {entry_id} in {loc.skill}'s learned layer."


def _promote_prompt(recurrence: int) -> str:
    return (
        f"This has come up ~{recurrence} times — promote it to a guaranteed always/never rule? "
        "Re-call with confirm:'promote' to make it a mandatory issue, or confirm:'keep' to leave "
        "it a learning."
    )


def _capture_promote_prompt(entry_id: str, recurrence: int) -> str:
    """Threshold prompt returned by ``capture``: promotion runs only through ``revise`` (§6)."""
    return (
        f"This has come up ~{recurrence} times — promote it to a guaranteed always/never rule? "
        f"Resolve with `revise(entry_id={entry_id!r}, action='promote', confirm='promote', "
        "body='<objective Always/Never rule>')`, or do nothing to keep it a learning."
    )


def _reject_missing_learning(loc: StoreLocation, entry_id: str, action: str) -> None:
    """Raise a clear error when an action needing a learning got an issue id or an unknown id."""
    if find_issue(loc, entry_id) is not None:
        raise ValueError(f"{action} applies to learnings; {entry_id!r} is an issue")
    raise ValueError(f"no learning with id {entry_id!r}")


def _conflict_result(
    loc: StoreLocation,
    run_id: str | None,
    polarity: str,
    conflict: tuple[IndexedEntry, str],
) -> dict:
    with_entry, explanation = conflict
    # Log the surfaced conflict against the entry it clashed with; nothing was committed.
    emit_capture(loc, run_id, with_entry.id, polarity, "conflict", scope=with_entry.scope)
    return {
        "status": "conflict",
        "entry_id": None,
        "conflict": {"with_id": with_entry.id, "explanation": explanation},
    }


# Words that mark an issue as a *prohibition* ("Never right-align …") rather than a mandate
# ("Always right-align …"). Only a prohibition can conflict with a learning that wants the same
# thing. This is a deliberate HEURISTIC: an embedding cannot separate "Always X" from "Never X"
# (both are ~identical vectors), so a high-similarity cross-polarity match is a real conflict only
# when the issue's phrasing forbids. False negatives (an oddly-worded prohibition) just miss a
# conflict — the user still resolves it via `revise` later — which is cheaper than crying conflict
# on an aligned mandate.
_PROHIBITION = re.compile(
    r"\b(never|don'?t|do not|avoid|refrain|without|no|not)\b", re.IGNORECASE
)


def _is_prohibition(title: str, body: str) -> bool:
    return bool(_PROHIBITION.search(f"{title} {body}"))


def _revise_skill_arg(skill: str, origin: str) -> str:
    """The literal ``skill`` argument a caller must pass to `revise` to reach an entry with this
    origin (§M7b, round-2 finding — routing global conflicts back through `revise` correctly).

    A ``"skill"``-origin entry lives in the store for the ``skill`` `recall` was called with, so
    that same string is the right target. A ``"global"``-origin entry lives in the reserved global
    store instead — `revise(skill, entry_id, ...)` always resolves ``entry_id`` against the store
    named by its ``skill`` argument, and the global store's ids are independently numbered from
    every per-skill store's (§M5e), so passing the calling skill's own name for a global entry
    would resolve the wrong local id (or miss entirely). ``GLOBAL_SLUG`` is the one string that
    reaches it.
    """
    return GLOBAL_SLUG if origin == "global" else skill


def _pairwise_conflict(
    skill: str,
    learning: RecalledLearning,
    issue: RecalledIssue,
    l_entry: IndexedEntry,
    i_entry: IndexedEntry,
    scope_phrase: dict[str, list[float]],
    config: Config,
) -> dict | None:
    """The full write-time conflict test (§7's ``_find_conflict``), applied to ONE learning/issue
    pair instead of one-candidate-vs-whole-store (§M7b): prohibition asymmetry, scope overlap, and
    the cosine cutoff.

    A conflict requires the ISSUE side to be a prohibition (``_is_prohibition`` on its title/body)
    and the LEARNING side to NOT be one — an avoidance learning agrees with a prohibiting issue
    rather than conflicting with it, mirroring ``_find_conflict``'s own asymmetry check. It also
    requires overlapping scope, exactly as ``_find_conflict`` does: the same scope, or the two
    scopes' phrase vectors clearing ``config.conflict_similarity`` — otherwise two similarly-worded
    entries that apply to genuinely different contexts (e.g. a "green checkmark" learning for
    successful transactions vs. an unrelated "never green checkmark" issue for error messages) would
    be flagged. Finally the two entries' own vectors must clear ``config.conflict_similarity``.

    ``skill`` is the skill name `recall` was called with — used only to compute each side's
    ``*_skill`` (see :func:`_revise_skill_arg`); it plays no part in the conflict test itself.
    """
    if _is_prohibition(l_entry.title, l_entry.body):
        return None
    if not _is_prohibition(i_entry.title, i_entry.body):
        return None
    if l_entry.scope != i_entry.scope:
        l_phrase = scope_phrase.get(l_entry.scope)
        i_phrase = scope_phrase.get(i_entry.scope)
        if (
            l_phrase is None
            or i_phrase is None
            or cosine(l_phrase, i_phrase) < config.conflict_similarity
        ):
            return None
    if cosine(l_entry.vector, i_entry.vector) < config.conflict_similarity:
        return None
    a_skill = _revise_skill_arg(skill, learning.origin)
    b_skill = _revise_skill_arg(skill, issue.origin)
    return {
        "a": learning.id,
        "a_origin": learning.origin,
        "a_skill": a_skill,
        "b": issue.id,
        "b_origin": issue.origin,
        "b_skill": b_skill,
        "note": (
            f"Learning {learning.id} ({learning.origin}) affirms what issue {issue.id} "
            f"({issue.origin}) forbids — the issue is mandatory (§5.2) and wins. Resolve via "
            f"`revise(skill={a_skill!r}, entry_id={learning.id!r}, ...)` or "
            f"`revise(skill={b_skill!r}, entry_id={issue.id!r}, ...)`."
        ),
    }


def _recall_conflicts(
    skill: str,
    snapshot: RetrievalSnapshot,
    g_snapshot: RetrievalSnapshot,
    learnings: list[RecalledLearning],
    issues: list[RecalledIssue],
    config: Config,
) -> list[dict]:
    """Many-vs-many conflict scan over ``recall``'s finalized returned set (§M7b).

    An OBSERVER pass, not a retrieval decision: called only after the skill/global union has already
    decided what to return, over that small already-selected list. Reads exclusively from
    ``snapshot``/``g_snapshot`` — the exact index rows the two ``retrieve()`` calls already read for
    THIS request (captured via their ``snapshot_out`` parameter) — so this never re-scans the store
    and never risks racing a concurrent capture/revise index rebuild that lands between `retrieve()`
    returning and this pass running. It never feeds back into ranking/MMR/the fallback floor. Only
    learning-vs-issue pairs are checked, mirroring the worked example this slice targets (a learning
    affirming what a co-returned issue forbids); issue-vs-issue and learning-vs-learning
    contradictions are out of scope here (the latter is a later slice, §M7c).

    ``skill`` is the skill name `recall` was called with (passed through to
    :func:`_pairwise_conflict` to compute each conflict's ``a_skill``/``b_skill`` — the correct
    `revise` target per side).

    Every pair here is (one learning, one issue) from two disjoint lists, so no symmetric A-vs-B /
    B-vs-A duplicate can arise structurally — nothing further to dedupe.
    """
    scope_phrase = {**g_snapshot.scope_phrase, **snapshot.scope_phrase}
    conflicts: list[dict] = []
    for learning in learnings:
        l_snapshot = g_snapshot if learning.origin == "global" else snapshot
        l_entry = l_snapshot.entries.get(learning.id)
        if l_entry is None:
            continue
        for issue in issues:
            i_snapshot = g_snapshot if issue.origin == "global" else snapshot
            i_entry = i_snapshot.entries.get(issue.id)
            if i_entry is None:
                continue
            hit = _pairwise_conflict(skill, learning, issue, l_entry, i_entry, scope_phrase, config)
            if hit is not None:
                conflicts.append(hit)
    return conflicts


def _find_conflict(
    loc,
    polarity: str,
    scope: str,
    candidate_title: str,
    candidate_body: str,
    candidate_vec: list[float],
    scope_vec: list[float],
    config,
) -> tuple[IndexedEntry, str] | None:
    """The nearest OPPOSITE-polarity PROHIBITION in an overlapping scope over the conflict cutoff.

    Cross-polarity only (§7): a new **learning** wanting what an existing **issue** forbids, and the
    symmetric new-issue-vs-existing-learning case. ``LEARNINGS``↔``LEARNINGS`` contradictions are
    NOT detected here — an embedding cannot reliably separate "duplicate" from "contradiction" for
    same-polarity text, so beyond dedup they are left as a documented limitation (§7) rather than a
    brittle detector. "Overlapping scope" mirrors dedup: same scope, or the other entry's scope
    phrase within ``conflict_similarity`` of the candidate's scope. A conflict requires the ISSUE
    side to FORBID what the LEARNING side AFFIRMS (both checked with :func:`_is_prohibition`): an
    ``Always …`` mandate agreeing with a learning is not flagged, and neither is an avoidance
    learning ("Prefer avoiding neon") lining up with a ``Never …`` issue — both forbid, so agree.
    """
    other = "issue" if polarity == "learning" else "learning"
    # A conflict requires the ISSUE side to FORBID what the LEARNING side AFFIRMS. Check the
    # candidate's own side: a new issue must be a prohibition; a new learning must NOT be one (an
    # avoidance learning agrees with a prohibiting issue rather than conflicting with it).
    candidate_is_prohibition = _is_prohibition(candidate_title, candidate_body)
    if polarity == "issue" and not candidate_is_prohibition:
        return None
    if polarity == "learning" and candidate_is_prohibition:
        return None
    scope_phrase = {s.scope: s.phrase for s in index.load_scopes(loc, other)}
    best: IndexedEntry | None = None
    best_sim = config.conflict_similarity
    for entry in index.load_entries(loc, other):
        if entry.scope != scope:
            phrase = scope_phrase.get(entry.scope)
            if phrase is None or cosine(scope_vec, phrase) < config.conflict_similarity:
                continue
        # The existing entry's side too: an existing issue must forbid; an existing learning must
        # affirm (an existing avoidance learning agrees with the new prohibiting issue).
        entry_is_prohibition = _is_prohibition(entry.title, entry.body)
        if polarity == "learning" and not entry_is_prohibition:
            continue
        if polarity == "issue" and entry_is_prohibition:
            continue
        sim = cosine(candidate_vec, entry.vector)
        if sim >= best_sim:
            best_sim = sim
            best = entry
    if best is None:
        return None
    if polarity == "learning":
        explanation = (
            f"New learning overlaps issue {best.id} in scope {scope!r}: the issue forbids what "
            f"this learning prefers. Resolve with `revise` — remove/demote {best.id}, or drop the "
            "learning."
        )
    else:
        explanation = (
            f"New issue overlaps learning {best.id} in scope {scope!r}: the mandatory rule forbids "
            f"what that learning prefers. Resolve with `revise` — weaken/remove/promote {best.id}."
        )
    return best, explanation


def _find_issue_conflict(
    loc,
    scope: str,
    candidate_title: str,
    candidate_body: str,
    candidate_vec: list[float],
    scope_vec: list[float],
    config,
) -> tuple[IndexedEntry, str] | None:
    """The nearest EXISTING issue in an overlapping scope that CONTRADICTS the new issue (§7).

    A contradiction is high similarity (>= ``conflict_similarity``) AND opposite prohibition-
    polarity — one forbids what the other mandates (a new ``Never X`` over an existing ``Always X``,
    or vice versa). Unlike learning<->learning, this is reliably detectable: :func:`_is_prohibition`
    heuristic separates ``Always`` from ``Never``, so a same-polarity near-duplicate (two ``Always
    X``) is left to dedup while only true opposite-polarity clashes surface as a conflict.
    "Overlapping scope" mirrors dedup: same scope, or the other issue's scope phrase within
    ``conflict_similarity`` of the candidate's scope.
    """
    candidate_is_prohibition = _is_prohibition(candidate_title, candidate_body)
    scope_phrase = {s.scope: s.phrase for s in index.load_scopes(loc, "issue")}
    best: IndexedEntry | None = None
    best_sim = config.conflict_similarity
    for entry in index.load_entries(loc, "issue"):
        if entry.scope != scope:
            phrase = scope_phrase.get(entry.scope)
            if phrase is None or cosine(scope_vec, phrase) < config.conflict_similarity:
                continue
        # Opposite prohibition-polarity only: two mandates (or two prohibitions) agree/dedup.
        if _is_prohibition(entry.title, entry.body) == candidate_is_prohibition:
            continue
        sim = cosine(candidate_vec, entry.vector)
        if sim >= best_sim:
            best_sim = sim
            best = entry
    if best is None:
        return None
    explanation = (
        f"New issue contradicts issue {best.id} in scope {scope!r}: one forbids what the other "
        f"mandates. Resolve with `revise` — remove/soften {best.id}, or drop the new rule."
    )
    return best, explanation


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


_USAGE = (
    "usage: whetstone [serve | compact (<skill> | --all) | promote <skill> <id> [--cluster] | "
    "export <skill> [--out <path>] | import <skill> <pack> [--merge|--replace] | doctor <skill>]"
)


def main(argv: list[str] | None = None) -> None:
    """Console entry point. No args (or ``serve``) runs the stdio MCP server as usual.

    Out-of-band maintenance subcommands (deliberately NOT part of the five-tool MCP surface — they
    are periodic/deliberate operator actions, never fired mid-task by the model):

    - ``compact <skill>`` — the maintenance pass (§7) + the M5a advisory behavioral report.
    - ``compact --all`` — compact every registered skill, then report cross-skill preference
      clusters as advisory ``global_candidate`` findings (§M5e). It never writes to the global
      store itself (§M7a) — promotion always asks a human; enact one with ``promote --cluster``.
    - ``promote <skill> <id>`` — lift one learning/issue into the learned global layer by hand
      (§M5e).
    - ``promote <skill> <id> --cluster`` — enact one cross-skill cluster a ``compact --all``
      ``global_candidate`` finding reported, naming its representative entry (§M7a).
    - ``export <skill> [--out <path>]`` — write a shareable preference pack (§M5c).
    - ``import <skill> <pack> [--merge|--replace]`` — import a preference pack, dedup-aware (§M5c).
    - ``doctor <skill>`` — read-only health check for the learned loop (§M5d); never edits anything.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] == "serve":
        mcp.run()
        return
    if args[0] == "compact":
        # Imported lazily so the hot ``serve`` path doesn't pull the compaction module.
        from .compaction import compact

        rest = args[1:]
        all_skills = "--all" in rest
        positional = [a for a in rest if a != "--all"]
        if all_skills and not positional:
            print(json.dumps(compact(all_skills=True), indent=2))
            return
        if not all_skills and len(positional) == 1:
            print(json.dumps(compact(positional[0]), indent=2))
            return
        print(_USAGE, file=sys.stderr)
        raise SystemExit(2)
    if args[0] == "promote":
        # `--cluster` is a flag in a FIXED trailing slot (`promote <skill> <id> [--cluster]`), not
        # filtered out of the argument list wherever it appears — a skill name is otherwise
        # unrestricted text, so a skill literally named "--cluster" must still parse as a normal
        # positional `skill` when it's not in that trailing slot.
        rest = args[1:]
        cluster = len(rest) == 3 and rest[2] == "--cluster"
        positional = rest[:2] if cluster else rest
        if len(positional) != 2:
            print(_USAGE, file=sys.stderr)
            raise SystemExit(2)
        skill_arg, id_arg = positional
        if cluster:
            from .promotion import promote_cluster

            print(json.dumps(promote_cluster(skill_arg, id_arg), indent=2))
        else:
            from .promotion import promote_to_global

            print(json.dumps(promote_to_global(skill_arg, id_arg), indent=2))
        return
    if args[0] == "export":
        rest = args[1:]
        out = None
        if "--out" in rest:
            i = rest.index("--out")
            if i + 1 >= len(rest):
                print(_USAGE, file=sys.stderr)
                raise SystemExit(2)
            out = rest[i + 1]
            rest = rest[:i] + rest[i + 2 :]
        if len(rest) != 1:
            print(_USAGE, file=sys.stderr)
            raise SystemExit(2)
        from .packs import export_pack

        print(json.dumps(export_pack(rest[0], out), indent=2))
        return
    if args[0] == "import":
        rest = args[1:]
        mode = "replace" if "--replace" in rest else "merge"
        positional = [a for a in rest if a not in ("--merge", "--replace")]
        if len(positional) != 2:
            print(_USAGE, file=sys.stderr)
            raise SystemExit(2)
        from .packs import import_pack

        print(json.dumps(import_pack(positional[0], positional[1], mode), indent=2))
        return
    if args[0] == "doctor":
        if len(args) != 2:
            print(_USAGE, file=sys.stderr)
            raise SystemExit(2)
        from .doctor import doctor

        print(json.dumps(doctor(args[1]), indent=2))
        return
    print(_USAGE, file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
