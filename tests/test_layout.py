"""Tests for store layout: lazy creation, attach idempotency, git, registry."""

from __future__ import annotations

import subprocess

import pytest

from whetstone.config import Config
from whetstone.store.layout import (
    attach_skill,
    ensure_store,
    is_store,
    read_registry,
    store_location,
)


@pytest.fixture
def cfg(tmp_path) -> Config:
    return Config(store_root=tmp_path)


def _git_log_count(path) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(path),
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


def test_ensure_store_creates_dirs_and_git_repo(cfg):
    result = ensure_store("great-tables", cfg)
    loc = result.location
    assert result.created is True
    assert loc.path.is_dir()
    assert loc.learnings_dir.is_dir()
    assert loc.issues_dir.is_dir()
    assert (loc.path / ".git").is_dir()
    assert _git_log_count(loc.path) == 1  # exactly one initial commit


def test_ensure_store_is_idempotent(cfg):
    first = ensure_store("great-tables", cfg)
    second = ensure_store("great-tables", cfg)
    assert first.created is True
    assert second.created is False
    assert first.location.path == second.location.path
    # No extra commits on re-ensure.
    assert _git_log_count(second.location.path) == 1


def test_skill_slug_isolates_store_dir(cfg):
    # A malicious skill name cannot escape the store root.
    loc = store_location("../../evil", cfg)
    assert loc.path.parent == cfg.store_root
    assert ".." not in loc.slug


def test_attach_returns_summary_and_registers(cfg):
    summary = attach_skill("great-tables", skill_path="/skills/great-tables", config=cfg)
    assert summary["skill"] == "great-tables"
    assert summary["slug"].startswith("great-tables-")
    assert summary["created"] is True
    assert summary["status"] == "attached"

    registry = read_registry(cfg)
    assert "great-tables" in registry
    assert registry["great-tables"]["slug"].startswith("great-tables-")
    assert registry["great-tables"]["skill_path"] == "/skills/great-tables"
    assert "attached_at" in registry["great-tables"]


def test_attach_twice_is_idempotent(cfg):
    first = attach_skill("great-tables", config=cfg)
    second = attach_skill("great-tables", config=cfg)
    assert first["status"] == "attached"
    assert second["status"] == "already_attached"
    assert second["created"] is False
    assert _git_log_count(second["path"]) == 1
    # Registry keeps a single record and a stable attached_at timestamp.
    registry = read_registry(cfg)
    assert list(registry) == ["great-tables"]


def test_partial_store_is_recovered(cfg):
    # Simulate an interruption after `git init` but before the baseline commit (.git, no HEAD).
    loc = store_location("interrupted", cfg)
    loc.path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(loc.path), check=True, capture_output=True)
    assert (loc.path / ".git").exists()
    assert not is_store(loc.path)  # no baseline commit yet

    result = ensure_store("interrupted", cfg)
    assert result.created is True
    assert is_store(loc.path)  # now has a baseline commit
    assert (loc.path / "learnings").is_dir()
    assert _git_log_count(loc.path) == 1


def test_concurrent_ensure_store_is_idempotent(cfg):
    # Parallel ensure_store() calls for the same skill must not race on git init/commit.
    import threading

    results: list = []
    errors: list = []

    def worker():
        try:
            results.append(ensure_store("concurrent", cfg))
        except Exception as exc:  # noqa: BLE001 - the test records any race failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(results) == 6
    assert sum(1 for r in results if r.created) == 1  # exactly one creator
    loc = store_location("concurrent", cfg)
    assert _git_log_count(loc.path) == 1  # exactly one baseline commit


def test_ensure_store_repairs_missing_scope_dirs(cfg):
    ensure_store("repairme", cfg)
    loc = store_location("repairme", cfg)
    # Simulate a store that lost its scope directories.
    import shutil

    shutil.rmtree(loc.learnings_dir)
    shutil.rmtree(loc.issues_dir)
    assert not loc.learnings_dir.exists()

    result = ensure_store("repairme", cfg)
    assert result.created is False  # still an existing store, just repaired
    assert loc.learnings_dir.is_dir()
    assert loc.issues_dir.is_dir()
