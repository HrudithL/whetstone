"""Tests for scope match, MMR diverse cap, uncapped/lower-cutoff issues, and the fallback floor."""

from __future__ import annotations

from dataclasses import replace

from conftest import make_issue, make_learning, seed
from whetstone.retrieval import retrieve
from whetstone.store import index


def _prepare(store, backend, learnings=(), issues=()):
    seed(store, learnings=learnings, issues=issues)
    index.rebuild_index(store, backend)


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


def test_weight_reflects_recurrence(store, backend, config):
    _prepare(
        store,
        backend,
        learnings=[make_learning("L1", "Right-align currency columns.", "currency", recurrence=3)],
    )
    learnings, _ = retrieve(store, "currency column alignment", backend, config)
    # weight = 1 - 1/(1+3) = 0.75
    assert learnings[0].weight == 0.75
