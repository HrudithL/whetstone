"""Tests for the derived sqlite index: build, rebuild-from-markdown reproducibility, staleness."""

from __future__ import annotations

import subprocess

import pytest

from conftest import make_issue, make_learning, seed
from whetstone.embeddings import cosine
from whetstone.store import index
from whetstone.store.index import entry_text


def test_rebuild_populates_scopes_and_entries(store, backend):
    seed(
        store,
        learnings=[
            make_learning("L1", "Right-align currency columns.", "currency columns"),
            make_learning("L2", "Prefer muted color palettes.", "color palette"),
        ],
        issues=[make_issue("I1", "Never band tiny tables.", "small tables")],
    )
    index.rebuild_index(store, backend)

    learning_scopes = {s.scope for s in index.load_scopes(store, "learning")}
    issue_scopes = {s.scope for s in index.load_scopes(store, "issue")}
    assert learning_scopes == {"currency columns", "color palette"}
    assert issue_scopes == {"small tables"}

    entries = {e.id: e for e in index.load_entries(store, "learning")}
    assert set(entries) == {"L1", "L2"}
    assert entries["L1"].recurrence == 1
    assert len(entries["L1"].vector) == backend.dim


def test_rebuild_is_reproducible_from_markdown(store, backend):
    seed(
        store,
        learnings=[make_learning("L1", "Right-align currency columns.", "currency columns")],
        issues=[make_issue("I1", "Never band tiny tables.", "small tables")],
    )
    index.rebuild_index(store, backend)
    first_entries = {e.id: e.vector for e in index.load_entries(store, "learning")}
    first_scopes = {s.scope: (s.centroid, s.phrase) for s in index.load_scopes(store, "learning")}

    # Rebuilding purely from the same markdown reproduces the identical stored vectors.
    index.rebuild_index(store, backend)
    second_entries = {e.id: e.vector for e in index.load_entries(store, "learning")}
    second_scopes = {s.scope: (s.centroid, s.phrase) for s in index.load_scopes(store, "learning")}

    assert first_entries == second_entries
    assert first_scopes == second_scopes


def test_stored_entry_vector_matches_backend_embedding(store, backend):
    learning = make_learning("L1", "Right-align currency columns.", "currency columns")
    seed(store, learnings=[learning])
    index.rebuild_index(store, backend)

    stored = index.load_entries(store, "learning")[0].vector
    expected = backend.embed([entry_text(learning.title, learning.body)])[0]
    assert stored == pytest.approx(expected, abs=1e-6)


def test_centroid_is_mean_of_entry_vectors(store, backend):
    seed(
        store,
        learnings=[
            make_learning("L1", "Right-align currency columns.", "money"),
            make_learning("L2", "Bold the currency totals.", "money"),
        ],
    )
    index.rebuild_index(store, backend)
    scope = next(s for s in index.load_scopes(store, "learning") if s.scope == "money")
    entries = index.load_entries(store, "learning")
    expected = [(a + b) / 2 for a, b in zip(entries[0].vector, entries[1].vector, strict=True)]
    assert scope.centroid == pytest.approx(expected, abs=1e-6)


def test_ensure_index_rebuilds_when_stale(store, backend):
    seed(store, learnings=[make_learning("L1", "First learning.", "scope-a")])
    index.ensure_index(store, backend)
    assert {e.id for e in index.load_entries(store, "learning")} == {"L1"}

    # Add markdown out-of-band; ensure_index detects the fingerprint change and rebuilds.
    seed(store, learnings=[make_learning("L2", "Second learning.", "scope-b")])
    index.ensure_index(store, backend)
    assert {e.id for e in index.load_entries(store, "learning")} == {"L1", "L2"}


def test_rebuild_temp_name_and_index_are_gitignored(store, backend):
    seed(store, learnings=[make_learning("L1", "A preference.", "scope-a")])
    index.rebuild_index(store, backend)

    # The live index and any crash-leftover temp (index.sqlite-*.tmp) match the store .gitignore,
    # so a rebuild never surfaces a tracked/untracked index file in git status.
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(store.path), check=True,
        capture_output=True, text=True,
    ).stdout
    assert "index.sqlite" not in status
    for name in ("index.sqlite", "index.sqlite-abc123.tmp"):
        ignored = subprocess.run(
            ["git", "check-ignore", name], cwd=str(store.path), capture_output=True, text=True
        )
        assert ignored.returncode == 0, f"{name} should be gitignored"


def test_empty_store_builds_empty_index(store, backend):
    index.ensure_index(store, backend)
    assert index.load_entries(store, "learning") == []
    assert index.load_entries(store, "issue") == []
    assert index.load_scopes(store, "learning") == []


def test_scope_matching_returns_expected_scopes(store, backend):
    seed(
        store,
        learnings=[
            make_learning("L1", "Right-align currency columns and format numbers.", "currency"),
            make_learning("L2", "Prefer muted, low-saturation color palettes.", "color palette"),
        ],
    )
    index.rebuild_index(store, backend)
    scopes = index.load_scopes(store, "learning")

    query = backend.embed(["formatting and aligning the currency columns of a table"])[0]
    sims = {s.scope: max(cosine(query, s.centroid), cosine(query, s.phrase)) for s in scopes}
    # The currency scope is clearly the closer match for a currency-formatting intent.
    assert sims["currency"] > sims["color palette"]
