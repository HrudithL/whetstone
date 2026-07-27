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


def test_negation_cancels_an_antonym_flip_into_agreement(env, monkeypatch):
    # A negation on only ONE side of an antonym pair often means the two AGREE ("avoid dark" ~
    # "use light"), not that they contradict -- round-2 Codex review finding. Must reinforce, not
    # flag, when the negation is in the SAME sentence as the matched antonym word.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt", "learning", "Avoid a dark background for the table.", "background tone", "prov-1"
    )

    result = capture(
        "gt", "learning", "Use a light background for the table.", "background tone", "prov-2"
    )

    assert result["status"] == "reinforced"


def test_unrelated_negation_elsewhere_does_not_mask_a_real_flip(env, monkeypatch):
    # The negation-cancellation above must be scoped to the SENTENCE containing the matched antonym
    # word -- an unrelated negation in another sentence of a multi-sentence body must not cancel a
    # genuine flip it has nothing to do with (round-2 Codex review finding).
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt",
        "learning",
        "Use a light background for the table. Keep the cell padding tight.",
        "background and padding",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Use a dark background for the table. Avoid extra cell padding.",
        "background and padding",
        "prov-2",
    )

    assert result["status"] == "possible_contradiction"


def test_relational_antonym_pairs_are_not_in_the_lexicon(env, monkeypatch):
    # before/after and above/below were dropped from _ANTONYM_PAIRS (round-2 Codex review finding):
    # a genuine paraphrase can reverse both the relation and its arguments ("totals above the
    # notes" == "notes below the totals"), which a bare word-presence check can't tell apart from a
    # real flip. Must reinforce normally, not flag.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt", "learning", "Put the totals above the notes in the summary table.",
        "totals placement", "prov-1",
    )

    result = capture(
        "gt", "learning", "Put the notes below the totals in the summary table.",
        "totals placement", "prov-2",
    )

    assert result["status"] == "reinforced"


def test_left_right_restricted_to_alignment_wording(env, monkeypatch):
    # Bare "left"/"right" is also a relational preposition ("put the legend left of the plot"),
    # with the same argument-order ambiguity before/after and above/below have -- round-3 Codex
    # review finding. Restricted to alignment wording (an "align"/"justify" cue in the same
    # sentence), so this relational use must reinforce normally, not flag.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt", "learning", "Put the legend to the left of the plot.", "legend placement", "prov-1"
    )

    result = capture(
        "gt", "learning", "Put the plot to the right of the legend.", "legend placement", "prov-2"
    )

    assert result["status"] == "reinforced"


def test_both_sides_locally_negated_with_a_shared_target_is_not_a_false_positive(env, monkeypatch):
    # Both antonym words locally negated can still agree when a shared explicit target reconciles
    # them ("avoid wide"/"avoid narrow", both funneling to "keep a medium width") -- round-3 Codex
    # review finding. Must reinforce normally, not flag.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt",
        "learning",
        "Avoid wide tables; keep the table at a medium width.",
        "table width",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Avoid narrow tables; keep the table at a medium width.",
        "table width",
        "prov-2",
    )

    assert result["status"] == "reinforced"


def test_possible_contradiction_includes_the_existing_entrys_body(env, monkeypatch):
    # The five-tool surface has no get-by-id lookup, so the payload must carry the EXISTING entry's
    # own wording, not just its id, for a caller to compare the two sides -- round-3 Codex review
    # finding.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
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

    assert result["status"] == "possible_contradiction"
    assert result["existing_body"] == "Right-align currency columns for a cleaner ledger look."


def test_unrelated_alignment_cue_elsewhere_does_not_trigger_left_right(env, monkeypatch):
    # A same-sentence "align" cue that has nothing to do with the matched "left"/"right" must not
    # count -- round-4 Codex review finding: the earlier fix only checked co-occurrence anywhere in
    # the sentence, not that the cue actually qualifies the side word (here it qualifies "title",
    # via "center-align", not the relational "left of the plot"/"right of the legend").
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt",
        "learning",
        "Put the legend left of the plot and center-align the title.",
        "legend and title layout",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Put the plot right of the legend and center-align the title.",
        "legend and title layout",
        "prov-2",
    )

    assert result["status"] == "reinforced"


def test_negation_scoping_uses_the_matched_alignment_occurrence(env, monkeypatch):
    # `left`/`right` can appear TWICE (once relational, once as a real alignment instruction) --
    # negation-scoping must check the clause that actually satisfied the alignment match, not just
    # the word's first occurrence anywhere in the text -- round-4 Codex review finding. "Never
    # left-align" ~ "right-align" agree (negating one alignment affirms the other), so this must
    # reinforce, not flag.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt",
        "learning",
        "Keep the legend left of the plot. Never left-align numeric columns.",
        "legend and column alignment",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Keep the legend left of the plot. Right-align numeric columns.",
        "legend and column alignment",
        "prov-2",
    )

    assert result["status"] == "reinforced"


def test_larger_smaller_is_not_in_the_lexicon(env, monkeypatch):
    # larger/smaller has the same argument-reversal ambiguity as the already-excluded before/after
    # and above/below pairs ("headings larger than body" == "body smaller than headings") -- round-4
    # Codex review finding. Must reinforce normally, not flag.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture("gt", "learning", "Make headings larger than body text.", "heading sizing", "prov-1")

    result = capture(
        "gt", "learning", "Make body text smaller than headings.", "heading sizing", "prov-2"
    )

    assert result["status"] == "reinforced"


def test_negation_cancellation_is_clause_scoped_not_sentence_scoped(env, monkeypatch):
    # Two clauses joined by "but" in ONE sentence can carry unrelated meanings -- a negation that
    # correctly cancels one antonym pair's flip must not also cancel an unrelated flip in a
    # different clause of the same sentence -- round-4 Codex review finding.
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    # This pair's hashing similarity (~0.56) falls just under the env fixture's 0.6 -- lower it
    # further so `_find_duplicate` reliably reaches the heuristic under test here.
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.5")
    capture(
        "gt",
        "learning",
        "Avoid a dark background, but use wide margins.",
        "background and margins",
        "prov-1",
    )

    result = capture(
        "gt",
        "learning",
        "Use a light background, but use narrow margins.",
        "background and margins",
        "prov-2",
    )

    # The background clause agrees (avoid dark ~ light); the margins clause genuinely flips
    # (wide vs narrow) and must still surface, not be masked by the background cancellation.
    assert result["status"] == "possible_contradiction"


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
