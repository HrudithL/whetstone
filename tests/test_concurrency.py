"""Concurrency + staleness safety for the storage/index layer (HashingBackend, no torch/network)."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from conftest import make_learning, seed
from whetstone.config import Config
from whetstone.embeddings import HashingBackend
from whetstone.server import capture, recall
from whetstone.store import index
from whetstone.store.access import load_issues, load_learnings
from whetstone.store.layout import store_location


def test_concurrent_captures_produce_unique_ids_and_lose_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    # Distinct, non-duplicate learnings across distinct scopes so each is a fresh committed entry.
    n = 12
    payloads = [
        ("learning", f"Distinct preference number {i} about layout.", f"scope-{i}")
        for i in range(n)
    ]

    def do(payload):
        polarity, body, scope = payload
        return capture("gt", polarity, body, scope, f"prov-{scope}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(do, payloads))

    assert all(r["status"] == "committed" for r in results)
    ids = [r["entry_id"] for r in results]
    assert len(set(ids)) == n, f"duplicate ids minted under concurrency: {ids}"

    slug = store_location("gt").slug
    loc = store_location("gt")
    persisted = load_learnings(loc)
    assert len(persisted) == n, "a concurrent capture was lost"
    assert {e.id for e in persisted} == set(ids)
    # Monotonic sequence with no gaps/dupes.
    assert sorted(int(e.id[1:]) for e in persisted) == list(range(1, n + 1))

    # The index rebuilt cleanly and reflects every entry (no missing-table / PK failure).
    backend = HashingBackend(dim=Config().embedding_dim)
    index.rebuild_index_if_stale(loc, backend)
    assert {e.id for e in index.load_entries(loc, "learning")} == set(ids)

    # Only markdown is committed; the derived index is not tracked.
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=str(tmp_path / slug), check=True, capture_output=True, text=True
    ).stdout
    assert "index.sqlite" not in tracked


def test_concurrent_recall_and_capture_never_sees_a_missing_index(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    capture("gt", "learning", "Seed learning about tables.", "tables", "prov")

    def recaller(_):
        # If a rebuild ever unlinked-then-wrote the live DB, a concurrent reader would hit
        # "no such table". With the atomic swap + write lock, every recall returns cleanly.
        return recall("gt", "table styling preferences")

    def capturer(i):
        return capture("gt", "learning", f"Another preference {i}.", f"scope-{i}", "prov")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for i in range(10):
            futures.append(pool.submit(recaller, i))
            futures.append(pool.submit(capturer, i))
        results = [f.result() for f in futures]

    # No exception surfaced from any recall/capture; recalls all produced a well-formed payload.
    recall_results = [r for r in results if "how_to_use" in r]
    assert recall_results
    assert all("run_id" in r for r in recall_results)


def test_changing_the_embedding_model_invalidates_the_index(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    from whetstone.store.layout import ensure_store

    config = Config(store_root=tmp_path, embedding_dim=64)
    ensure_store("gt", config)
    loc = store_location("gt", config)
    seed(loc, learnings=[make_learning("L1", "Right-align currency columns.", "currency")])

    class FakeBackend(HashingBackend):
        """Same dim/class, different declared model id AND different vectors per model."""

        def __init__(self, model_id: str, rotate: int, dim: int = 64):
            super().__init__(dim=dim)
            self._fake_model_id = model_id
            self._rotate = rotate

        @property
        def model_id(self) -> str:
            return self._fake_model_id

        def embed(self, texts):
            # A model-specific rotation so different models yield different vectors of the same dim.
            r = self._rotate
            return [vec[r:] + vec[:r] for vec in super().embed(texts)]

    backend_a = FakeBackend("model-a", rotate=1)
    index.ensure_index(loc, backend_a)
    vectors_a = {e.id: e.vector for e in index.load_entries(loc, "learning")}

    # Switching to a different model of the SAME dimensionality must invalidate + rebuild the index,
    # not silently reuse model-a's incompatible vectors.
    backend_b = FakeBackend("model-b", rotate=3)
    index.ensure_index(loc, backend_b)
    vectors_b = {e.id: e.vector for e in index.load_entries(loc, "learning")}

    assert vectors_a["L1"] != vectors_b["L1"], "index was not rebuilt after the model changed"
    body = "Right-align currency columns."
    expected_b = backend_b.embed([index.entry_text(body[:40], body)])[0]
    assert vectors_b["L1"] == pytest.approx(expected_b, abs=1e-6)


def test_fingerprint_is_stable_when_nothing_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    from whetstone.store.layout import ensure_store

    config = Config(store_root=tmp_path, embedding_dim=64)
    ensure_store("gt", config)
    loc = store_location("gt", config)
    seed(loc, learnings=[make_learning("L1", "Prefer muted palettes.", "color")])
    backend = HashingBackend(dim=64)

    index.ensure_index(loc, backend)
    first = {e.id: e.vector for e in index.load_entries(loc, "learning")}
    # A second ensure with an unchanged store + backend must NOT rebuild to different vectors.
    index.ensure_index(loc, backend)
    second = {e.id: e.vector for e in index.load_entries(loc, "learning")}
    assert first == second
    assert load_issues(loc) == []
