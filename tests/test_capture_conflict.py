"""Cross-polarity conflict detection in `capture` (§7).

A new entry whose text is >= conflict_similarity to an existing OPPOSITE-polarity entry in an
overlapping scope is surfaced as `{status: "conflict"}` and NOT committed — the user resolves it
with `revise`. Both directions are covered; learning<->learning conflicts are a documented
limitation and are not asserted here. The Always/Never pair used here scores ~0.91 on the hashing
backend, above the default 0.85 conflict cutoff, so no override is needed.
"""

from __future__ import annotations

import subprocess

import pytest

from whetstone.server import capture
from whetstone.store.access import load_issues, load_learnings
from whetstone.store.layout import store_location


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    return tmp_path


def _commit_count(root, slug) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(root / slug),
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


def test_new_learning_conflicts_with_existing_issue(env):
    capture(
        "gt",
        "issue",
        "Never right-align the currency columns.",
        "currency columns",
        "prov",
    )
    slug = store_location("gt").slug
    before = _commit_count(env, slug)

    result = capture(
        "gt",
        "learning",
        "Right-align the currency columns.",
        "currency columns",
        "prov",
    )

    assert result["status"] == "conflict"
    assert result["entry_id"] is None
    assert result["conflict"]["with_id"] == "I1"
    assert result["conflict"]["explanation"]
    # The conflicting learning was NOT committed.
    assert load_learnings(store_location("gt")) == []
    assert _commit_count(env, slug) == before


def test_new_issue_conflicts_with_existing_learning(env):
    capture(
        "gt",
        "learning",
        "Right-align the currency columns.",
        "currency columns",
        "prov",
    )
    slug = store_location("gt").slug
    before = _commit_count(env, slug)

    result = capture(
        "gt",
        "issue",
        "Never right-align the currency columns.",
        "currency columns",
        "prov",
    )

    assert result["status"] == "conflict"
    assert result["conflict"]["with_id"] == "L1"
    assert load_issues(store_location("gt")) == []
    assert _commit_count(env, slug) == before


def test_unrelated_opposite_polarity_entry_is_not_a_conflict(env):
    capture("gt", "issue", "Never band tables under ten rows.", "small tables", "prov")

    result = capture(
        "gt",
        "learning",
        "Use a muted blue color palette for the table.",
        "color palette",
        "prov",
    )

    # Different scope and dissimilar text -> a normal commit, no conflict.
    assert result["status"] == "committed"
    assert result["entry_id"] == "L1"


def test_conflict_is_surfaced_regardless_of_supervision_mode(env, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SUPERVISION", "autonomous")
    capture(
        "gt",
        "issue",
        "Never right-align the currency columns.",
        "currency columns",
        "prov",
    )
    result = capture(
        "gt",
        "learning",
        "Right-align the currency columns.",
        "currency columns",
        "prov",
    )
    assert result["status"] == "conflict"


def test_aligned_always_issue_is_not_a_conflict(env):
    # An "Always X" mandate AGREES with a learning wanting X — high similarity but NOT a conflict.
    # (Only a prohibition can conflict; an embedding can't tell "Always X" from "Never X".)
    capture(
        "gt",
        "issue",
        "Always right-align the currency columns.",
        "currency columns",
        "prov",
    )
    result = capture(
        "gt",
        "learning",
        "Right-align the currency columns.",
        "currency columns",
        "prov",
    )
    assert result["status"] == "committed"
    assert result["entry_id"] == "L1"


def test_new_prohibition_issue_conflicts_but_aligned_mandate_does_not(env):
    # Symmetric check on the new-issue side: a "Never" issue over an existing learning conflicts,
    # while an "Always" issue over the same learning does not.
    capture("gt", "learning", "Right-align the currency columns.", "currency columns", "prov")

    aligned = capture(
        "gt", "issue", "Always right-align the currency columns.", "currency columns", "prov"
    )
    assert aligned["status"] == "committed"  # aligned mandate, no conflict

    forbidding = capture(
        "gt", "issue", "Never right-align the currency columns.", "currency columns", "prov"
    )
    assert forbidding["status"] == "conflict"
    assert forbidding["conflict"]["with_id"] == "L1"


def test_conflict_wins_over_same_polarity_issue_dedup_noop(env, monkeypatch):
    # A prohibiting "Never X" issue that is a near-duplicate of an aligned "Always X" issue must
    # surface its conflict with an existing "X" learning, not be silently nooped by dedup. Lowering
    # the dedup cutoff makes the Always/Never pair a dedup candidate, so this fails without the
    # conflict-before-dedup ordering.
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")
    capture("gt", "learning", "Right-align the currency columns.", "currency columns", "prov")
    capture("gt", "issue", "Always right-align the currency columns.", "currency columns", "prov")

    forbidding = capture(
        "gt", "issue", "Never right-align the currency columns.", "currency columns", "prov"
    )
    assert forbidding["status"] == "conflict"  # not "noop"
    assert forbidding["conflict"]["with_id"] == "L1"


def test_aligned_negative_learning_is_not_a_conflict_but_affirmative_is(env, monkeypatch):
    # A conflict needs one side to AFFIRM what the other FORBIDS. An avoidance learning agrees with
    # a prohibiting issue, so it must not be flagged — even though it clears the (lowered) cutoff;
    # only its prohibition phrasing excludes it. An affirmative learning still conflicts.
    monkeypatch.setenv("WHETSTONE_CONFLICT_SIMILARITY", "0.6")
    capture("gt", "issue", "Never right-align the currency columns.", "currency columns", "prov")

    aligned = capture(
        "gt", "learning", "Avoid right-aligning the currency columns.", "currency columns", "prov"
    )
    assert aligned["status"] == "committed"  # both forbid -> agree, not a conflict

    affirmative = capture(
        "gt", "learning", "Right-align the currency columns.", "currency columns", "prov"
    )
    assert affirmative["status"] == "conflict"
    assert affirmative["conflict"]["with_id"] == "I1"


def test_new_never_issue_does_not_conflict_with_an_avoidance_learning(env, monkeypatch):
    # Symmetric direction: a new prohibiting issue over an EXISTING avoidance learning is agreement.
    monkeypatch.setenv("WHETSTONE_CONFLICT_SIMILARITY", "0.6")
    capture(
        "gt", "learning", "Avoid right-aligning the currency columns.", "currency columns", "prov"
    )
    result = capture(
        "gt", "issue", "Never right-align the currency columns.", "currency columns", "prov"
    )
    assert result["status"] == "committed"  # both forbid -> agree, not a conflict
