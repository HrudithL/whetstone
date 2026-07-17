"""Tests for store layout: lazy creation, attach idempotency, git, registry."""

from __future__ import annotations

import subprocess

import pytest

from whetstone.config import Config
from whetstone.store.layout import (
    attach_skill,
    ensure_store,
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
