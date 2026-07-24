"""M5d — visibility (capture/revise confirmation payload) + the doctor diagnostic."""

from __future__ import annotations

import pytest

from whetstone.doctor import doctor
from whetstone.server import capture, recall, revise
from whetstone.store.layout import store_location


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    monkeypatch.setenv("WHETSTONE_CONSULT_GLOBAL", "false")
    return tmp_path


# --------------------------------------------------------------------------- visibility


def test_capture_committed_returns_confirmation(env):
    res = capture("gt", "learning", "Right-align currency columns.", "currency columns", "prov")
    assert res["status"] == "committed"
    assert "Captured" in res["confirmation"]
    assert "currency columns" in res["confirmation"]
    assert "gt" in res["confirmation"]


def test_capture_reinforced_returns_confirmation(env):
    capture("gt", "learning", "Right-align currency columns.", "currency columns", "prov")
    res = capture("gt", "learning", "Right-align currency columns.", "currency columns", "prov")
    assert res["status"] == "reinforced"
    assert "Reinforced" in res["confirmation"]


def test_revise_returns_confirmation(env):
    capture("gt", "learning", "Right-align currency columns.", "currency columns", "prov")
    res = revise("gt", "L1", "reinforce")
    assert res["status"] == "reinforced"
    assert res["confirmation"] == "Reinforced L1 in gt's learned layer."


def test_revise_needs_confirmation_has_no_confirmation(env):
    capture("gt", "issue", "Never band tiny tables.", "small tables", "prov")
    # weaken on an issue always prompts first — nothing committed, so no confirmation.
    res = revise("gt", "I1", "weaken")
    assert res["status"] == "needs_confirmation"
    assert "confirmation" not in res


def test_confirmation_truncates_long_body(env):
    long_body = "Right-align currency columns " * 10
    res = capture("gt", "learning", long_body, "currency", "prov")
    assert res["confirmation"].count("Re-applies") == 1
    assert "…" in res["confirmation"]  # the gist was elided


# --------------------------------------------------------------------------- doctor


def test_doctor_reports_missing_store(env):
    report = doctor("never-touched")
    assert report["exists"] is False
    assert report["loop_healthy"] is False
    assert "operating_instructions" in report
    assert "No store" in report["diagnosis"]


def test_doctor_reports_dead_loop(env):
    # A store seeded ONLY via capture (no recall ever) — the loop looks unwired.
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    report = doctor("gt")
    assert report["exists"] is True
    assert report["loop_healthy"] is False
    assert report["events"]["by_type"].get("recall", 0) == 0
    assert "operating_instructions" in report
    assert "recall" in report["operating_instructions"]


def test_doctor_reports_healthy_loop(env):
    recall("gt", "styling a table with currency columns")
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    report = doctor("gt")
    assert report["exists"] is True
    assert report["loop_healthy"] is True
    assert report["events"]["by_type"]["recall"] >= 1
    assert report["learnings"] == 1
    assert "operating_instructions" not in report
    assert "healthy" in report["diagnosis"].lower()


def test_doctor_never_mutates(env):
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    loc = store_location("gt")
    import subprocess

    before = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=str(loc.path), capture_output=True, text=True
    ).stdout
    doctor("gt")
    after = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=str(loc.path), capture_output=True, text=True
    ).stdout
    assert before == after  # no new commits — doctor is read-only
