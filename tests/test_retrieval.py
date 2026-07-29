"""Tests for scope match, MMR diverse cap, uncapped/lower-cutoff issues, and the fallback floor."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date

from conftest import make_issue, make_learning, seed
from whetstone.retrieval import _MAX_CLAUSES, _intent_clauses, retrieve
from whetstone.store import index


def _prepare(store, backend, learnings=(), issues=()):
    seed(store, learnings=learnings, issues=issues)
    index.rebuild_index(store, backend)


def test_intent_clauses_single_topic_intent_is_unsplit():
    # Nothing to split -> exactly the original intent, so a single-topic caller embeds/matches
    # precisely as before the clause-decomposition change.
    assert _intent_clauses("formatting the currency columns") == ["formatting the currency columns"]


def test_intent_clauses_splits_on_commas_and_semicolons_and_keeps_the_whole_intent():
    intent = "Styling a table: color palette; row banding, currency formatting"
    clauses = _intent_clauses(intent)
    assert clauses[0] == intent  # whole intent always first/kept
    assert "Styling a table: color palette" in clauses  # split on ";", not ":"
    assert "row banding" in clauses
    assert "currency formatting" in clauses
    assert len(clauses) == len(set(clauses))  # deduped


def test_intent_clauses_dedupes_repeated_clauses():
    # A trailing near-empty fragment or a repeated phrase must not produce duplicate query vectors.
    assert _intent_clauses("color palette, color palette,") == ["color palette, color palette,",
                                                                  "color palette"]


def test_intent_clauses_keeps_the_sole_surviving_clause():
    # Regression (caught by review): an earlier version bailed out to [intent] whenever fewer than
    # two RAW split parts survived the word-count filter, discarding the one usable clause a
    # two-part intent reduces to once its one-word fragment ("caps") is filtered out — exactly the
    # dilution this function exists to prevent. "header emphasis" must still be probed on its own.
    clauses = _intent_clauses("caps, header emphasis")
    assert clauses[0] == "caps, header emphasis"
    assert "header emphasis" in clauses
    assert "caps" not in clauses


def test_intent_clauses_caps_total_count():
    # `intent` is a caller-controlled MCP argument; an adversarial or just very long, heavily-
    # punctuated one must not blow the embed-batch size up unboundedly (real memory/CPU cost per
    # clause). A pathological intent with 100 distinct two-word clauses still yields at most
    # _MAX_CLAUSES query vectors (the full intent + capped clauses), not 101.
    intent = ", ".join(f"topic {i}" for i in range(100))
    clauses = _intent_clauses(intent)
    assert len(clauses) == _MAX_CLAUSES
    assert clauses[0] == intent


def test_matched_scope_learnings_are_returned(store, backend, config):
    _prepare(
        store,
        backend,
        learnings=[
            make_learning("L1", "Right-align currency columns and format numbers.", "currency"),
            make_learning("L2", "Prefer muted, low-saturation color palettes.", "color palette"),
        ],
    )
    learnings, _ = retrieve(
        store, "formatting and aligning the currency columns", backend, config
    )
    ids = {x.id for x in learnings}
    assert "L1" in ids  # the currency scope matches the currency-formatting intent


def test_mmr_returns_a_diverse_subset_not_k_near_duplicates(store, backend, config):
    # Three near-identical learnings plus two distinct ones, all in one (matched) scope.
    cluster = [
        make_learning("L1", "Use a muted blue color palette for the table.", "styling"),
        make_learning("L2", "Apply a muted blue color palette to the table.", "styling"),
        make_learning("L3", "The table should use a muted blue color palette.", "styling"),
    ]
    distinct = [
        make_learning("L4", "Right-align every numeric currency column.", "styling"),
        make_learning("L5", "Add subtle horizontal row banding.", "styling"),
    ]
    _prepare(store, backend, learnings=cluster + distinct)

    cfg = replace(config, mmr_lambda=0.7)
    learnings, _ = retrieve(store, "muted blue color palette", backend, cfg, learnings_k=3)
    picked = {x.id for x in learnings}
    assert len(picked) == 3  # respects learnings_k
    # MMR must not return three near-duplicates; at least one distinct learning is included.
    assert picked & {"L4", "L5"}


def test_learnings_k_caps_the_count(store, backend, config):
    learnings = [
        make_learning(f"L{i}", f"Styling preference number {i} for tables.", "styling")
        for i in range(1, 11)
    ]
    _prepare(store, backend, learnings=learnings)
    got, _ = retrieve(store, "styling preference for tables", backend, config, learnings_k=4)
    assert len(got) == 4


def test_negative_learnings_k_is_clamped_on_the_matched_path(store, backend, config):
    learnings = [
        make_learning(f"L{i}", f"Styling preference number {i} for tables.", "styling")
        for i in range(1, 6)
    ]
    _prepare(store, backend, learnings=learnings)
    # A negative cap must not hit Python negative-slice semantics; it clamps to an empty result.
    got, _ = retrieve(store, "styling preference for tables", backend, config, learnings_k=-1)
    assert got == []


def test_negative_learnings_k_does_not_flood_the_fallback(store, backend, config):
    learnings = [
        make_learning(f"L{i}", f"Preference {i}.", f"scope-{i}", recurrence=i) for i in range(1, 6)
    ]
    _prepare(store, backend, learnings=learnings)
    # Off-topic intent -> fallback path, where a naive [:-1] slice would return all-but-one.
    got, _ = retrieve(store, "writing a bash script to parse logs", backend, config, learnings_k=-1)
    assert got == []


def test_issues_are_uncapped(store, backend, config):
    issues = [
        make_issue(f"I{i}", f"Never do the forbidden styling thing number {i}.", "styling")
        for i in range(1, 16)
    ]
    _prepare(store, backend, issues=issues)
    _, got = retrieve(store, "styling thing forbidden", backend, config, learnings_k=2)
    assert len(got) == 15  # every matched issue returns; learnings_k does not touch issues


def test_issues_use_the_lower_cutoff(store, backend, config):
    # A learning and an issue with the same body/scope embed identically, so their scope-similarity
    # to the intent is equal. With a high learnings cutoff and a low issues cutoff, only the issue
    # clears — proving the asymmetric cutoffs (§5.4).
    body = "Handle the currency column alignment carefully."
    _prepare(
        store,
        backend,
        learnings=[make_learning("L1", body, "currency")],
        issues=[make_issue("I1", body, "currency")],
    )
    cfg = replace(config, learnings_cutoff=0.99, issues_cutoff=0.05)
    learnings, issues = retrieve(store, "currency column alignment", backend, cfg)
    assert [x.id for x in learnings] == []
    assert [x.id for x in issues] == ["I1"]


def test_fallback_floor_returns_non_empty_for_off_topic_intent(store, backend, config):
    _prepare(
        store,
        backend,
        learnings=[
            make_learning("L1", "Prefer muted color palettes.", "color palette", recurrence=5),
            make_learning("L2", "Right-align currency columns.", "currency", recurrence=1),
        ],
        issues=[make_issue("I1", "Never band tiny tables.", "small tables")],
    )
    learnings, issues = retrieve(
        store, "writing a bash script to parse rotated log files", backend, config
    )
    assert learnings, "fallback floor should surface top-weight learnings"
    assert issues, "fallback floor should surface broadly-scoped issues"
    # Top-weight learning leads the fallback.
    assert learnings[0].id == "L1"


def test_empty_store_retrieves_empty(store, backend, config):
    index.rebuild_index(store, backend)
    learnings, issues = retrieve(store, "anything at all", backend, config)
    assert learnings == []
    assert issues == []


def test_load_helpers_share_one_snapshot_across_a_rebuild(store, backend):
    # retrieve() reads all rows through ONE open connection so a concurrent index rebuild (atomic
    # os.replace) cannot straddle it. An already-open connection keeps reading its inode across the
    # replace, so it sees a single consistent snapshot; a fresh connection sees the new file.
    _prepare(store, backend, learnings=[make_learning("L1", "First learning.", "styling")])

    conn = sqlite3.connect(str(index.index_path(store)))
    try:
        before = index.load_entries(store, "learning", conn)
        assert {e.id for e in before} == {"L1"}

        # Rebuild with a second entry (os.replace swaps the file to a new inode).
        seed(store, learnings=[make_learning("L2", "Second learning.", "styling")])
        index.rebuild_index(store, backend)

        # The still-open connection reads its original snapshot; a fresh one sees the rebuild.
        assert {e.id for e in index.load_entries(store, "learning", conn)} == {"L1"}
        assert {e.id for e in index.load_entries(store, "learning")} == {"L1", "L2"}
    finally:
        conn.close()


def test_weight_reflects_recurrence(store, backend, config):
    _prepare(
        store,
        backend,
        learnings=[make_learning("L1", "Right-align currency columns.", "currency", recurrence=3)],
    )
    # Decay off isolates the recurrence term: weight = r = 1 - 1/(1+3) = 0.75.
    cfg = replace(config, learnings_decay=False)
    learnings, _ = retrieve(store, "currency column alignment", backend, cfg)
    assert learnings[0].weight == 0.75


def test_weight_decays_with_staleness(store, backend, config):
    # Same recurrence, different last_seen: the fresh learning must out-weigh the stale one, and the
    # stale one is discounted by recency (§4.4). H defaults to 180 days.
    fresh = replace(
        make_learning("L1", "Right-align currency columns.", "currency", recurrence=5),
        last_seen=date(2026, 7, 1),
    )
    stale = replace(
        make_learning("L2", "Drop vertical gridlines on currency.", "currency", recurrence=5),
        last_seen=date(2025, 7, 1),
    )
    _prepare(store, backend, learnings=[fresh, stale])
    today = date(2026, 7, 1)
    learnings, _ = retrieve(store, "currency column alignment and gridlines", backend, config,
                            today=today)
    by_id = {x.id: x.weight for x in learnings}
    # Fresh (Δ=0): weight = r*1 = 1 - 1/6 ≈ 0.8333.
    assert by_id["L1"] == round(1 - 1 / 6, 4)
    # Stale (Δ=365, H=180): recency = 0.5**(365/180) < 0.5, so its weight is well below the fresh.
    assert by_id["L2"] < by_id["L1"]
    assert by_id["L2"] < 0.5 * by_id["L1"]
