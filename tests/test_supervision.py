"""The §9 supervision dial across `capture` and `revise`, in all three modes.

- supervised: every new/changed entry is held behind a needs_confirmation until confirm:true.
- balanced (default): clear, non-conflicting changes commit silently.
- autonomous: routine changes commit silently.
Independent of the dial, promotion and issue-contradiction removals ALWAYS prompt (§6).
"""

from __future__ import annotations

import pytest

from conftest import make_issue, make_learning, seed
from whetstone.server import capture, revise
from whetstone.store.access import find_learning, load_learnings
from whetstone.store.layout import commit_store


def _clean_seed(loc, learnings=(), issues=()) -> None:
    seed(loc, learnings=learnings, issues=issues)
    commit_store(loc, "seed")


# --------------------------------------------------------------------------- capture matrix


def test_supervised_capture_holds_a_new_entry_until_confirmed(store, config, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "supervised")

    held = capture("gt", "learning", "Prefer muted palettes.", "color", "prov")
    assert held["status"] == "needs_confirmation"
    assert load_learnings(store) == []  # nothing committed

    done = capture("gt", "learning", "Prefer muted palettes.", "color", "prov", confirm=True)
    assert done["status"] == "committed"
    assert done["entry_id"] == "L1"


def test_balanced_capture_commits_silently(store, config):
    # Default mode is balanced.
    result = capture("gt", "learning", "Prefer muted palettes.", "color", "prov")
    assert result["status"] == "committed"


def test_autonomous_capture_commits_silently(store, config, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "autonomous")
    result = capture("gt", "issue", "Never use neon.", "color", "prov")
    assert result["status"] == "committed"


# --------------------------------------------------------------------------- revise matrix


def test_supervised_revise_holds_a_reinforcement(store, config, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "supervised")
    _clean_seed(store, learnings=[make_learning("L1", "Prefer muted palettes.", "color")])

    held = revise("gt", "L1", "reinforce")
    assert held["status"] == "needs_confirmation"
    assert find_learning(store, "L1").recurrence == 1  # not bumped

    done = revise("gt", "L1", "reinforce", confirm=True)
    assert done == {"status": "reinforced", "entry_id": "L1", "recurrence": 2}


def test_balanced_revise_reinforces_silently(store, config):
    _clean_seed(store, learnings=[make_learning("L1", "Prefer muted palettes.", "color")])
    result = revise("gt", "L1", "reinforce")
    assert result["status"] == "reinforced"


def test_autonomous_revise_reinforces_silently(store, config, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "autonomous")
    _clean_seed(store, learnings=[make_learning("L1", "Prefer muted palettes.", "color")])
    result = revise("gt", "L1", "reinforce")
    assert result["status"] == "reinforced"


# --------------------------------------------------------------------------- always-prompt cases


def test_promote_prompts_even_in_autonomous_mode(store, config, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "autonomous")
    _clean_seed(store, learnings=[make_learning("L1", "Prefer muted palettes.", "color")])

    result = revise("gt", "L1", "promote", body="Never use non-muted palettes.")
    assert result["status"] == "needs_confirmation"
    assert "promote" in result["prompt"]


def test_issue_contradiction_prompts_even_in_autonomous_mode(store, config, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "autonomous")
    _clean_seed(store, issues=[make_issue("I1", "Never use neon colors.", "color")])

    result = revise("gt", "I1", "remove")
    assert result["status"] == "needs_confirmation"
    assert "hard rule" in result["prompt"]


@pytest.mark.parametrize("mode", ["supervised", "balanced", "autonomous"])
def test_learning_remove_follows_the_dial(store, config, monkeypatch, mode):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", mode)
    _clean_seed(store, learnings=[make_learning("L1", "Prefer muted palettes.", "color")])

    result = revise("gt", "L1", "remove")
    if mode == "supervised":
        assert result["status"] == "needs_confirmation"
        assert find_learning(store, "L1") is not None
    else:
        assert result == {"status": "removed", "entry_id": "L1"}


def test_supervised_confirm_cancel_does_not_perform_the_mutation(store, config, monkeypatch):
    # A non-empty confirm string is NOT blanket assent — a supervised remove with confirm:"cancel"
    # must still hold, not proceed. Only confirm:true releases the supervision gate.
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "supervised")
    _clean_seed(store, learnings=[make_learning("L1", "Prefer muted palettes.", "color")])

    result = revise("gt", "L1", "remove", confirm="cancel")
    assert result["status"] == "needs_confirmation"
    assert find_learning(store, "L1") is not None  # not removed
