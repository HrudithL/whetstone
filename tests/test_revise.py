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
from whetstone.server import capture, revise
from whetstone.store.access import find_issue, find_learning, load_issues, load_learnings
from whetstone.store.layout import commit_store, store_location
from whetstone.telemetry import read_events


@pytest.fixture
def fixed_today(monkeypatch):
    """Pin `revise`'s clock so seeded/rewritten dates are deterministic (matches M2a)."""
    stamp = date(2026, 7, 17)
    monkeypatch.setattr("whetstone.server._today", lambda: stamp)
    return stamp


@pytest.fixture
def env_only(tmp_path, monkeypatch):
    """Point the server's own load_config() at a temp store root; store is created lazily."""
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    return tmp_path


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


def test_reinforce_applies_supplied_body_and_scope(store, config):
    _clean_seed(store, learnings=[_muted("L1", 1)])

    result = revise(
        "gt", "L1", "reinforce", body="Prefer deeply muted, low-saturation palettes.", scope="theme"
    )

    assert result["status"] == "reinforced"
    entry = find_learning(store, "L1")
    assert entry.recurrence == 2  # still reinforced
    assert entry.body == "Prefer deeply muted, low-saturation palettes."  # prose updated
    assert entry.scope == "theme"  # scope moved
    # The old scope file no longer carries L1 (moved, not duplicated).
    assert [e.id for e in load_learnings(store)] == ["L1"]


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
    # The prompt points at revise (there is no `promote` tool).
    assert "revise" in result["prompt"]
    assert find_learning(store, "L1") is not None  # not moved


def test_promote_declined_with_keep_does_not_promote(store, config):
    _clean_seed(store, learnings=[_muted("L1", 2)])
    revise("gt", "L1", "promote", body="Never use non-muted palettes.")  # first prompt

    # A declining answer must NOT be read as assent (regression: any non-empty string promoted).
    result = revise("gt", "L1", "promote", body="Never use non-muted palettes.", confirm="keep")
    assert result == {"status": "unchanged", "entry_id": "L1", "recurrence": 2}
    assert find_learning(store, "L1") is not None  # still a learning
    assert find_issue(store, "I1") is None  # nothing promoted


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


# --------------------------------------------------------------------------- monotonic ids


def test_ids_are_never_reused_after_remove_promote_demote(env_only):
    # Two learnings; remove the top one -> the next capture must NOT reuse L2.
    assert capture("gt", "learning", "A muted blue palette.", "color", "p")["entry_id"] == "L1"
    assert capture("gt", "learning", "Serif captions please.", "type", "p")["entry_id"] == "L2"
    revise("gt", "L2", "remove")
    assert capture("gt", "learning", "Bold the header row.", "header", "p")["entry_id"] == "L3"

    # Promote L3 -> I1 (removes L3); a later learning must not reuse L3.
    revise("gt", "L3", "promote", body="Never leave the header unbolded.", confirm="promote")
    assert capture("gt", "learning", "Roomier cell padding.", "density", "p")["entry_id"] == "L4"

    # Demote I1 -> a fresh learning (L5, not a reused number); a later issue must not reuse I1.
    demoted = revise("gt", "I1", "demote", confirm=True)
    assert demoted["entry_id"] == "L5"
    assert capture("gt", "issue", "Never use comic sans.", "type", "p")["entry_id"] == "I2"


def test_next_ids_is_git_tracked(env_only):
    capture("gt", "learning", "A muted blue palette.", "color", "p")
    loc = store_location("gt")
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=str(loc.path), check=True, capture_output=True, text=True
    ).stdout
    assert "next_ids.json" in tracked


# ------------------------------------------------------------------- capture -> revise promote


def test_capture_threshold_resolves_via_revise_promote(env_only, monkeypatch):
    # The promotion threshold is surfaced by capture but executed only by revise (single source).
    monkeypatch.setenv("WHETSTONE_PROMOTION_THRESHOLD", "2")
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")
    body = "Right-align the currency columns for clean tables."
    assert capture("gt", "learning", body, "currency", "p")["status"] == "committed"

    hit = capture("gt", "learning", "Please right-align the currency columns for clean tables.",
                  "currency", "p")
    assert hit["status"] == "needs_confirmation"
    assert hit["recurrence"] == 2
    assert "revise" in hit["prompt"] and "promote" in hit["prompt"]
    # The reinforcement is committed even though promotion is deferred.
    assert find_learning(store_location("gt"), hit["entry_id"]).recurrence == 2

    # Resolve the promotion via revise with a reworded objective body — runs against the id, never a
    # re-dedup of the reworded text.
    done = revise("gt", hit["entry_id"], "promote",
                  body="Always right-align currency columns.", confirm="promote")
    assert done["status"] == "promoted"
    assert find_learning(store_location("gt"), hit["entry_id"]) is None
    assert find_issue(store_location("gt"), done["entry_id"]).body == (
        "Always right-align currency columns."
    )
