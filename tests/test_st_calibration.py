"""Sentence-transformers calibration suite — the semantic behavior the hashing stand-in can't check.

The main suite runs on the deterministic ``HashingBackend`` (fast, offline). That verifies all the
*logic* — storage, git, id allocation, revise flows, telemetry — but it cannot verify that the
*real* embeddings actually produce good similarity behavior, because the similarity thresholds
(``dedup_similarity``, ``conflict_similarity``, retrieval cutoffs) are calibrated for the
``sentence-transformers`` backend, not for hashing.

These tests drive the real ``all-MiniLM-L6-v2`` model end-to-end through ``capture``/``recall`` and
assert the semantic outcomes: a paraphrase dedups, genuinely different preferences stay separate, a
cross-polarity contradiction is flagged, and recall ranks the in-scope entry first. Every wording
here was chosen with empirical cosine margin against the current (provisional) thresholds so the
assertions are stable, not knife-edge. They run only when the ``[embeddings]`` extra is installed
(skipped otherwise) and are marked ``embeddings`` so CI can run them as a separate, cached job:
``pytest -m embeddings`` (ST job) vs ``pytest -m "not embeddings"`` (fast hashing job).
"""

from __future__ import annotations

import pytest

from whetstone.server import capture, recall
from whetstone.store.index import load_entries
from whetstone.store.layout import store_location

pytestmark = pytest.mark.embeddings


@pytest.fixture(autouse=True)
def _require_sentence_transformers():
    # Skip at setup (NOT a module-level importorskip) so collection still finishes and the four
    # `embeddings`-marked tests are collected. In a base/dev env without the extra, `pytest -m
    # embeddings` then reports clean skips instead of pytest's no-tests-collected exit status.
    pytest.importorskip("sentence_transformers")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point the server's load_config() at a temp store root and pin the calibrated ST backend.

    The cosine-margin wordings below are calibrated for ``all-MiniLM-L6-v2``, so pin both the
    backend and the model, and isolate config (empty ``XDG_CONFIG_HOME``) so an ambient
    ``WHETSTONE_EMBEDDING_MODEL`` / ``config.toml`` can't silently swap the model or the thresholds
    and make these margins meaningless.
    """
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    monkeypatch.setenv("WHETSTONE_EMBEDDING_BACKEND", "sentence-transformers")
    monkeypatch.setenv("WHETSTONE_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


def test_paraphrase_dedup_reinforces(env):
    """A reworded restatement of the same preference reinforces the original (cos ~0.98 >= 0.9),
    rather than creating a second near-duplicate learning — the exact case hashing lets slip."""
    first = capture(
        "gt",
        "learning",
        "Right-align currency columns and use a thousands separator with two decimal places.",
        "currency columns",
        "prov",
    )
    assert first["status"] == "committed"

    again = capture(
        "gt",
        "learning",
        "Right-align the currency columns; use thousands separators and two decimal places.",
        "currency columns",
        "prov",
    )
    assert again["status"] == "reinforced"
    assert again["entry_id"] == first["entry_id"]
    assert again["recurrence"] == 2

    loc = store_location("gt", _load(env))
    assert len(load_entries(loc, "learning")) == 1, "the paraphrase must not create a new entry"


def test_distinct_preferences_stay_separate(env):
    """Genuinely different preferences (cos ~0.11 << 0.9) stay separate. Both are filed under the
    SAME scope on purpose: `_find_duplicate` skips non-overlapping scopes before comparing vectors,
    so a differently-scoped pair would pass even if the bodies were near-identical. Same scope makes
    the body-vector threshold this case claims to calibrate actually run."""
    a = capture(
        "gt",
        "learning",
        "Right-align currency columns and use thousands separators.",
        "table styling",
        "prov",
    )
    b = capture(
        "gt",
        "learning",
        "Use muted, colorblind-safe palettes for categorical fills.",
        "table styling",
        "prov",
    )
    assert a["status"] == "committed"
    assert b["status"] == "committed"
    assert a["entry_id"] != b["entry_id"]
    assert len(load_entries(store_location("gt", _load(env)), "learning")) == 2


def test_cross_polarity_conflict_detected(env):
    """A new issue that forbids what an existing learning prefers (cos ~0.92 >= 0.85, opposite
    polarity) surfaces as a conflict instead of committing silently."""
    capture(
        "gt",
        "learning",
        "Use bright neon accent colors to emphasize key figures in the table.",
        "accent color",
        "prov",
    )
    clash = capture(
        "gt",
        "issue",
        "Do not use bright neon accent colors to emphasize key figures in the table.",
        "accent color",
        "prov",
    )
    assert clash["status"] == "conflict"
    assert clash["conflict"]["with_id"].startswith("L")


def test_recall_ranks_relevant_scope_first(env):
    """An elaborated intent about one scope ranks that scope's learning first via real similarity
    matching. The relevant (currency) entry is captured LAST, after two distractors, and all three
    have equal weight — so `retrieve()`'s no-match fallback (top-weight in insertion order) would
    surface a distractor first. Currency ranking first can therefore only come from actual
    scope/embedding matching, not the fallback path."""
    capture(
        "gt",
        "learning",
        "Use muted, colorblind-safe palettes for categorical fills.",
        "color palette",
        "prov",
    )
    capture(
        "gt",
        "learning",
        "Band alternating rows with a light gray fill in dense tables.",
        "row banding",
        "prov",
    )
    capture(
        "gt",
        "learning",
        "Right-align currency columns and use thousands separators with two decimals.",
        "currency columns",
        "prov",
    )

    result = recall(
        "gt",
        "formatting a table's monetary currency columns: figure alignment and thousands separators",
    )
    assert result["learnings"], "the currency learning should be retrieved"
    assert result["learnings"][0]["scope"] == "currency columns"


def _load(store_root):
    """The same Config the server sees (temp store root + ST backend), for direct store reads."""
    from whetstone.config import load_config

    return load_config()
