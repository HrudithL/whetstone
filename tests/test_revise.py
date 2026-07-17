"""End-to-end tests for the M2b `revise` tool: every action and needs_confirmation branch.

Entries are seeded straight to markdown (the source of truth) and addressed by id, so these tests
exercise the mutation/confirmation logic without depending on embedding similarity. The default
`balanced` supervision mode is assumed unless a test overrides it (see test_supervision.py for the
dial matrix).
"""

from __future__ import annotations

import subprocess
from datetime import date

import pytest

from conftest import make_issue, make_learning, seed
from whetstone.server import revise
from whetstone.store.access import find_issue, find_learning, load_issues, load_learnings
from whetstone.store.layout import commit_store
from whetstone.telemetry import read_events


@pytest.fixture
def fixed_today(monkeypatch):
    """Pin `revise`'s clock so seeded/rewritten dates are deterministic (matches M2a)."""
    stamp = date(2026, 7, 17)
    monkeypatch.setattr("whetstone.server._today", lambda: stamp)
    return stamp


def _commit_count(loc) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(loc.path),
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


def _clean_seed(loc, learnings=(), issues=()) -> None:
    """Seed entries and commit, so a following revise adds exactly one commit off a clean tree."""
    seed(loc, learnings=learnings, issues=issues)
    commit_store(loc, "seed")


def _muted(entry_id: str, recurrence: int = 1):
    return make_learning(entry_id, "Prefer muted palettes.", "color", recurrence=recurrence)


# --------------------------------------------------------------------------- reinforce


def test_reinforce_bumps_recurrence_and_commits(store, config, fixed_today):
    _clean_seed(store, learnings=[_muted("L1")])
    before = _commit_count(store)

    result = revise("gt", "L1", "reinforce")

    assert result == {"status": "reinforced", "entry_id": "L1", "recurrence": 2}
    assert _commit_count(store) == before + 1
    (entry,) = load_learnings(store)
    assert entry.recurrence == 2
    assert entry.last_seen == fixed_today
    # The mutation emitted a revise event.
    events = [e for e in read_events(store) if e["type"] == "revise"]
    assert events[-1] == {
        **events[-1],
        "action": "reinforce",
        "entry_id": "L1",
        "status": "reinforced",
    }


def test_reinforce_at_threshold_returns_promotion_prompt(store, config, monkeypatch, fixed_today):
    monkeypatch.setenv("WHETSTONE_PROMOTION_THRESHOLD", "4")
    _clean_seed(store, learnings=[_muted("L1", 3)])

    result = revise("gt", "L1", "reinforce")

    assert result["status"] == "needs_confirmation"
    assert result["recurrence"] == 4
    assert "promote" in result["prompt"]
    # The reinforcement is still applied even though a prompt was returned (§6).
    assert find_learning(store, "L1").recurrence == 4


def test_reinforce_confirm_promote_moves_to_issue(store, config, monkeypatch, fixed_today):
    monkeypatch.setenv("WHETSTONE_PROMOTION_THRESHOLD", "4")
    _clean_seed(store, learnings=[_muted("L1", 3)])
    revise("gt", "L1", "reinforce")  # -> recurrence 4, prompt

    result = revise(
        "gt", "L1", "reinforce", body="Never use non-muted palettes.", confirm="promote"
    )

    assert result["status"] == "promoted"
    assert result["entry_id"] == "I1"
    assert find_learning(store, "L1") is None
    issue = find_issue(store, "I1")
    assert issue.body == "Never use non-muted palettes."


def test_reinforce_confirm_keep_stays_a_learning(store, config, monkeypatch, fixed_today):
    monkeypatch.setenv("WHETSTONE_PROMOTION_THRESHOLD", "4")
    _clean_seed(store, learnings=[_muted("L1", 3)])
    revise("gt", "L1", "reinforce")  # -> recurrence 4, prompt

    result = revise("gt", "L1", "reinforce", confirm="keep")

    assert result == {"status": "reinforced", "entry_id": "L1", "recurrence": 4}
    # confirm:"keep" does not bump again — recurrence stays at 4.
    assert find_learning(store, "L1").recurrence == 4


def test_reinforce_on_an_issue_id_is_rejected(store, config):
    _clean_seed(store, issues=[make_issue("I1", "Never use neon.", "color")])
    with pytest.raises(ValueError, match="learnings"):
        revise("gt", "I1", "reinforce")


# --------------------------------------------------------------------------- weaken


def test_weaken_decrements_recurrence_without_refreshing_last_seen(store, config):
    seeded = _muted("L1", 3)
    _clean_seed(store, learnings=[seeded])

    result = revise("gt", "L1", "weaken")

    assert result == {"status": "revised", "entry_id": "L1", "recurrence": 2}
    entry = find_learning(store, "L1")
    assert entry.recurrence == 2
    assert entry.last_seen == seeded.last_seen  # weaken must NOT refresh recency


def test_weaken_below_zero_prompts_then_keep_resets_to_one(store, config):
    _clean_seed(store, learnings=[_muted("L1", 0)])

    prompt = revise("gt", "L1", "weaken")
    assert prompt["status"] == "needs_confirmation"
    assert "keep" in prompt["prompt"]
    # Nothing persisted yet — still at recurrence 0.
    assert find_learning(store, "L1").recurrence == 0

    kept = revise("gt", "L1", "weaken", confirm="keep")
    assert kept == {"status": "revised", "entry_id": "L1", "recurrence": 1}
    assert find_learning(store, "L1").recurrence == 1


def test_weaken_below_zero_confirm_remove_deletes(store, config):
    _clean_seed(store, learnings=[_muted("L1", 0)])
    revise("gt", "L1", "weaken")  # below-0 prompt

    removed = revise("gt", "L1", "weaken", confirm="remove")
    assert removed == {"status": "removed", "entry_id": "L1"}
    assert find_learning(store, "L1") is None


# --------------------------------------------------------------------------- remove


def test_remove_deletes_a_learning(store, config):
    _clean_seed(store, learnings=[_muted("L1")])
    before = _commit_count(store)

    result = revise("gt", "L1", "remove")

    assert result == {"status": "removed", "entry_id": "L1"}
    assert load_learnings(store) == []
    assert _commit_count(store) == before + 1


def test_remove_unknown_id_raises(store, config):
    with pytest.raises(ValueError, match="no entry"):
        revise("gt", "L99", "remove")


# --------------------------------------------------------------------------- promote (direct)


def test_promote_always_prompts_first_then_confirm_moves_polarity(store, config):
    _clean_seed(store, learnings=[_muted("L1", 2)])

    prompt = revise("gt", "L1", "promote", body="Never use non-muted palettes.")
    assert prompt["status"] == "needs_confirmation"
    assert "promote" in prompt["prompt"]
    # Not moved until confirmed.
    assert find_learning(store, "L1") is not None

    done = revise("gt", "L1", "promote", body="Never use non-muted palettes.", confirm=True)
    assert done["status"] == "promoted"
    assert done["entry_id"] == "I1"
    # Polarity moved, body rewritten, scoring fields dropped (issues have none).
    assert find_learning(store, "L1") is None
    issue = find_issue(store, "I1")
    assert issue.body == "Never use non-muted palettes."
    assert issue.scope == "color"
    assert not hasattr(issue, "recurrence")


def test_promote_confirmed_without_body_asks_for_rewording(store, config):
    _clean_seed(store, learnings=[_muted("L1")])
    revise("gt", "L1", "promote")  # first prompt

    result = revise("gt", "L1", "promote", confirm=True)  # confirmed but no body
    assert result["status"] == "needs_confirmation"
    assert "rewording" in result["prompt"]
    assert find_learning(store, "L1") is not None  # not moved


# --------------------------------------------------------------------------- demote (direct)


def test_demote_seeds_learning_at_three(store, config, monkeypatch, fixed_today):
    monkeypatch.setenv("WHETSTONE_DEMOTE_SEED_RECURRENCE", "3")
    _clean_seed(store, issues=[make_issue("I1", "Never use neon colors.", "color")])
    before = _commit_count(store)

    result = revise("gt", "I1", "demote")

    assert result == {"status": "demoted", "entry_id": "L1", "recurrence": 3}
    assert find_issue(store, "I1") is None
    learning = find_learning(store, "L1")
    assert learning.recurrence == 3
    assert learning.first_seen == fixed_today
    assert learning.last_seen == fixed_today
    assert _commit_count(store) == before + 1
    events = [e for e in read_events(store) if e["type"] == "revise"]
    assert events[-1]["action"] == "demote"
    assert events[-1]["status"] == "demoted"


def test_demote_on_a_learning_id_is_rejected(store, config):
    _clean_seed(store, learnings=[_muted("L1")])
    with pytest.raises(ValueError, match="issues"):
        revise("gt", "L1", "demote")


# --------------------------------------------------------------------------- issue contradiction


def test_weaken_issue_is_a_three_way_prompt_remove(store, config):
    _clean_seed(store, issues=[make_issue("I1", "Never use neon colors.", "color")])

    prompt = revise("gt", "I1", "weaken")
    assert prompt["status"] == "needs_confirmation"
    assert "hard rule" in prompt["prompt"]

    removed = revise("gt", "I1", "weaken", confirm="remove")
    assert removed == {"status": "removed", "entry_id": "I1"}
    assert load_issues(store) == []


def test_remove_issue_demote_softens(store, config, monkeypatch, fixed_today):
    monkeypatch.setenv("WHETSTONE_DEMOTE_SEED_RECURRENCE", "3")
    _clean_seed(store, issues=[make_issue("I1", "Never use neon colors.", "color")])
    revise("gt", "I1", "remove")  # 3-way prompt

    result = revise("gt", "I1", "remove", confirm="demote", body="Prefer avoiding neon colors.")
    assert result == {"status": "demoted", "entry_id": "L1", "recurrence": 3}
    assert find_issue(store, "I1") is None
    assert find_learning(store, "L1").body == "Prefer avoiding neon colors."


def test_issue_contradiction_cancel_makes_no_change(store, config):
    _clean_seed(store, issues=[make_issue("I1", "Never use neon colors.", "color")])
    before = _commit_count(store)

    result = revise("gt", "I1", "weaken", confirm="cancel")
    assert result == {"status": "unchanged", "entry_id": "I1"}
    assert find_issue(store, "I1") is not None
    assert _commit_count(store) == before  # nothing committed


def test_unknown_action_raises(store, config):
    with pytest.raises(ValueError, match="action must be"):
        revise("gt", "L1", "bogus")
