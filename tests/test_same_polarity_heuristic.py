"""§M7c — the same-polarity (learning-vs-learning) antonym/negation heuristic in ``capture``'s
dedup path.

``_find_duplicate`` already found these two texts to be a same/close-scope near-duplicate above
``dedup_similarity`` — this heuristic asks a materially different, narrower question on top of that:
does the wording actually flip (an antonym pair, or a negation on only one side), i.e. is this a
literal contradiction that happens to embed similarly rather than a genuine restatement? When it
fires, ``capture`` returns ``possible_contradiction`` (a signal only — nothing is written, the
existing entry is untouched) instead of silently reinforcing. This is config-gated
(``same_polarity_contradiction_check``, default on per the M7c calibration — see
``harness/calibration/labels.yaml``'s ``same_polarity_contradiction`` set and
``harness/calibrate.py``'s ``calibrate_same_polarity_contradiction``); when off, behavior is
byte-identical to pre-M7c ``capture`` regardless of content.
"""

from __future__ import annotations

import subprocess

import pytest

from whetstone.server import capture
from whetstone.store.access import load_learnings
from whetstone.store.layout import store_location


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    # The hashing backend scores these single-word-substituted paraphrases lower than the
    # sentence-transformers-calibrated default (0.9) -- see harness/calibrate.py's
    # calibrate_same_polarity_contradiction docstring for the measured range (~0.71-0.94). Lower the
    # dedup cutoff so `_find_duplicate` reliably finds the pair first, exactly like the existing
    # dedup tests in tests/test_recall_capture.py.
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")
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


# --------------------------------------------------------------------------- fires (contradiction)


def test_antonym_pair_asymmetry_is_flagged_and_not_reinforced(env, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt",
        "learning",
        "Right-align currency columns for a cleaner ledger look.",
        "currency columns",
        "prov-1",
    )
    slug = store_location("gt").slug
    before = _commit_count(env, slug)

    result = capture(
        "gt",
        "learning",
        "Left-align currency columns for a cleaner ledger look.",
        "currency columns",
        "prov-2",
    )

    assert result["status"] == "possible_contradiction"
    assert result["entry_id"] == "L1"
    assert result["candidate_body"] == "Left-align currency columns for a cleaner ledger look."
    assert "note" in result and result["note"]

    # Nothing written: no new commit, the original entry's recurrence is untouched.
    assert _commit_count(env, slug) == before
    [learning] = load_learnings(store_location("gt"))
    assert learning.recurrence == 1


def test_negation_asymmetry_is_flagged(env, monkeypatch):
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt", "learning", "Apply subtle zebra striping to wide tables.", "row banding", "prov-1"
    )

    result = capture(
        "gt", "learning", "Never apply zebra striping to wide tables.", "row banding", "prov-2"
    )

    assert result["status"] == "possible_contradiction"
    assert result["entry_id"] == "L1"


# --------------------------------------------------------------------------- does not fire (dup)


def test_genuine_paraphrase_still_reinforces_normally(env, monkeypatch):
    # Regression check (§7): the heuristic being enabled must not disturb the ordinary case.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt",
        "learning",
        "Right-align currency columns and show two decimal places.",
        "currency columns",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Please right-align the currency columns with two decimal places.",
        "currency columns",
        "prov-2",
    )

    assert result["status"] == "reinforced"
    assert result["entry_id"] == "L1"
    assert result["recurrence"] == 2


def test_antonym_words_mentioned_on_both_sides_is_not_a_false_positive(env, monkeypatch):
    # Tricky near-miss: BOTH texts mention "left" and "right" -- symmetric, not a flip.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt",
        "learning",
        "Keep left and right padding equal around numeric columns.",
        "numeric column padding",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Keep the left and right padding balanced around numeric columns.",
        "numeric column padding",
        "prov-2",
    )

    assert result["status"] == "reinforced"


def test_negation_on_both_sides_is_not_a_false_positive(env, monkeypatch):
    # Tricky near-miss: BOTH texts are negated ("avoid" / "never") -- symmetric, not a flip.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt", "learning", "Avoid neon accent colors in the table.", "neon color avoidance", "prov-1"
    )

    result = capture(
        "gt", "learning", "Never use neon accent colors in the table.", "neon color avoidance", "p2"
    )

    assert result["status"] == "reinforced"


# --------------------------------------------------------------------------- config gate


def test_flag_off_falls_back_to_silent_reinforce_regardless_of_content(env, monkeypatch):
    # Even textbook antonym content must NOT be flagged when the check is disabled -- capture falls
    # back to exactly today's dedup-reinforce behavior.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "false")
    capture(
        "gt",
        "learning",
        "Right-align currency columns for a cleaner ledger look.",
        "currency columns",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Left-align currency columns for a cleaner ledger look.",
        "currency columns",
        "prov-2",
    )

    assert result["status"] == "reinforced"
    assert result["entry_id"] == "L1"
    assert result["recurrence"] == 2


def test_only_applies_to_learnings_not_issues(env, monkeypatch):
    # The hook is only wired into the `polarity == "learning"` branch (§M7c scope) -- a
    # same-polarity ISSUE near-duplicate keeps its existing `noop` behavior, even with antonym text.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt", "issue", "Never left-align currency columns in financial reports.",
        "currency columns", "prov-1",
    )

    result = capture(
        "gt", "issue", "Never right-align currency columns in financial reports.",
        "currency columns", "prov-2",
    )

    # Same-polarity issue<->issue is a dedup noop when it doesn't clear the cross-polarity /
    # issue<->issue CONTRADICTION checks first; here the two aren't opposite prohibition-polarity
    # (both are "Never ..."), so it falls through to the ordinary same-polarity issue noop.
    assert result["status"] == "noop"
    assert result["entry_id"] == "I1"
