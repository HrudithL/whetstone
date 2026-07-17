"""Integration test: the attach tool is registered and drives the store end-to-end."""

from __future__ import annotations

import asyncio
import subprocess

from whetstone.server import attach, mcp


def test_m1_tools_are_registered_on_the_server():
    names = [t.name for t in asyncio.run(mcp.list_tools())]
    # M0's attach plus the M1 recall/capture loop. (revise/metrics arrive in M2.)
    assert set(names) == {"attach", "recall", "capture"}


def test_attach_tool_creates_a_git_backed_store(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    result = attach("great-tables", path="/skills/great-tables")

    assert result["status"] == "attached"
    store = tmp_path / result["slug"]  # slug is bounded + hash-suffixed for collision safety
    assert store.parent == tmp_path
    assert (store / "learnings").is_dir()
    assert (store / "issues").is_dir()
    assert (store / ".git").is_dir()

    count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(store),
        check=True,
        capture_output=True,
        text=True,
    )
    assert int(count.stdout.strip()) == 1

    # Idempotent through the tool surface.
    again = attach("great-tables")
    assert again["status"] == "already_attached"
