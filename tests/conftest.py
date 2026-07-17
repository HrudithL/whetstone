"""Shared fixtures. Embedding-dependent tests use the small HashingBackend (no torch/network)."""

from __future__ import annotations

from datetime import date

import pytest

from whetstone.config import Config
from whetstone.embeddings import HashingBackend
from whetstone.store.access import save_issue, save_learning
from whetstone.store.entries import IssueEntry, LearningEntry
from whetstone.store.layout import ensure_store, store_location


@pytest.fixture
def backend() -> HashingBackend:
    return HashingBackend(dim=256)


@pytest.fixture
def config(tmp_path, monkeypatch) -> Config:
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    return Config(store_root=tmp_path, embedding_dim=256)


@pytest.fixture
def store(config):
    """A freshly initialized, empty store for skill 'gt'."""
    ensure_store("gt", config)
    return store_location("gt", config)


def make_learning(entry_id: str, body: str, scope: str, recurrence: int = 1) -> LearningEntry:
    return LearningEntry(
        id=entry_id,
        title=body[:40],
        body=body,
        scope=scope,
        provenance="test",
        recurrence=recurrence,
        first_seen=date(2026, 1, 1),
        last_seen=date(2026, 1, 1),
    )


def make_issue(entry_id: str, body: str, scope: str) -> IssueEntry:
    return IssueEntry(id=entry_id, title=body[:40], body=body, scope=scope, provenance="test")


def seed(loc, learnings=(), issues=()) -> None:
    for entry in learnings:
        save_learning(loc, entry)
    for entry in issues:
        save_issue(loc, entry)
