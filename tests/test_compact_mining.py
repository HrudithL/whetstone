"""M5a — behavioral mining folded into compact: the four advisory rules, the report, and --all."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import make_learning, seed
from whetstone.compaction import compact
from whetstone.config import Config
from whetstone.server import capture, recall, revise
from whetstone.store.access import load_learnings
from whetstone.store.layout import (
    GLOBAL_SLUG,
    ensure_store,
    global_store_location,
    store_location,
)
from whetstone.telemetry import append_event

TODAY = date(2026, 7, 24)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    # Keep thresholds small + deterministic for the mining rules under test.
    monkeypatch.setenv("WHETSTONE_HARDEN_REINFORCEMENTS", "3")
    monkeypatch.setenv("WHETSTONE_STALE_RUNS", "4")
    monkeypatch.setenv("WHETSTONE_GLOBAL_SKILL_COUNT", "3")
    # Disable the global layer while seeding per-skill stores so recall doesn't pull it in.
    monkeypatch.setenv("WHETSTONE_CONSULT_GLOBAL", "false")
    return tmp_path


def _rules(result):
    return {f["rule"] for f in result["findings"]}


# --------------------------------------------------------------------------- harden


def test_harden_candidate_flagged(env):
    res = capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    lid = res["entry_id"]
    for _ in range(3):
        revise("gt", lid, "reinforce")

    result = compact("gt")
    harden = [f for f in result["findings"] if f["rule"] == "harden"]
    assert len(harden) == 1
    assert harden[0]["id"] == lid
    assert harden[0]["evidence"]["reinforcements"] >= 3


def test_harden_not_flagged_when_weakened(env):
    res = capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    lid = res["entry_id"]
    for _ in range(3):
        revise("gt", lid, "reinforce")
    revise("gt", lid, "weaken")  # a single contradiction disqualifies it

    assert "harden" not in _rules(compact("gt"))


# --------------------------------------------------------------------------- bad capture


def test_bad_capture_churn_flagged(env):
    # Two committed learnings in one scope + a weaken there = churn.
    capture("gt", "learning", "Use teal accents for headers.", "accent color", "prov")
    r2 = capture("gt", "learning", "Use amber accents for totals.", "accent color", "prov")
    revise("gt", r2["entry_id"], "weaken")

    bad = [f for f in compact("gt")["findings"] if f["rule"] == "bad_capture"]
    assert len(bad) == 1
    assert bad[0]["scope"] == "accent color"
    assert bad[0]["evidence"]["committed_learnings"] >= 2
    assert bad[0]["evidence"]["weaken_or_remove"] >= 1


# --------------------------------------------------------------------------- stale (usage-based)


def test_stale_never_surfaced_flagged(env, monkeypatch):
    # A present learning that recall never returns across >= stale_runs runs.
    loc = store_location("gt")
    ensure_store("gt")
    seed(loc, learnings=[make_learning("L1", "An obscure niche preference.", "obscure niche")])
    for _ in range(5):  # >= stale_runs=4 recalls on an unrelated intent
        recall("gt", "completely unrelated topic about deployment pipelines")

    stale = [f for f in compact("gt", today=TODAY)["findings"] if f["rule"] == "stale"]
    assert any(f["id"] == "L1" for f in stale)


# --------------------------------------------------------------------------- conflict residue


def _emit_conflict(loc, entry_id):
    """Seed a `conflict` capture event directly (the ST-calibrated detector won't fire under the
    hashing backend, so we test the mining rule in isolation from conflict *detection*)."""
    append_event(
        loc,
        {"type": "capture", "run_id": "r-x", "entry_id": entry_id, "polarity": "issue",
         "status": "conflict", "scope": "palette"},
    )


def test_conflict_residue_flagged(env):
    capture("gt", "learning", "Prefer bright neon palettes.", "palette", "prov")
    _emit_conflict(store_location("gt"), "L1")  # a conflict surfaced against the present learning

    residue = [f for f in compact("gt")["findings"] if f["rule"] == "conflict_residue"]
    assert len(residue) == 1
    assert residue[0]["id"] == "L1"  # the learning it clashed with


def test_conflict_residue_cleared_after_revise(env):
    capture("gt", "learning", "Prefer bright neon palettes.", "palette", "prov")
    _emit_conflict(store_location("gt"), "L1")
    revise("gt", "L1", "reinforce")  # any revise on L1 counts as resolving it

    assert "conflict_residue" not in _rules(compact("gt"))


# --------------------------------------------------------------------------- report file + advisory


def test_findings_written_to_report_and_never_committed(env):
    res = capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    for _ in range(3):
        revise("gt", res["entry_id"], "reinforce")

    result = compact("gt")
    report = store_location("gt").path / "compact-report.md"
    assert result["report_path"] == str(report)
    assert report.exists()
    assert "advisory" in report.read_text(encoding="utf-8")
    # It is git-ignored — the report is never part of the committed store.
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "compact-report.md"],
        cwd=str(store_location("gt").path),
        capture_output=True,
        text=True,
    )
    assert tracked.stdout.strip() == ""


def test_mining_is_advisory_only_no_mutation(env):
    res = capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    lid = res["entry_id"]
    for _ in range(3):
        revise("gt", lid, "reinforce")

    compact("gt")  # a harden finding fires, but nothing is auto-promoted
    learnings = load_learnings(store_location("gt"))
    assert [x.id for x in learnings] == [lid]  # still a learning, unchanged


# ----------------------------------------------------------------------- compact --all promotion


def test_compact_all_promotes_cross_skill_cluster(env):
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", body, "palette", "prov")

    result = compact(all_skills=True)

    assert result["all"] is True
    promotions = result["promotions"]
    assert len(promotions) == 1
    assert set(promotions[0]["skills"]) == {"gt", "web", "ppt"}
    # The per-skill copies are retired; the survivor lives in the global store.
    for skill in ("gt", "web", "ppt"):
        assert load_learnings(store_location(skill)) == []
    g_learnings = load_learnings(global_store_location(Config(store_root=env, embedding_dim=384)))
    assert len(g_learnings) == 1
    assert "muted" in g_learnings[0].body


def test_compact_all_ignores_below_threshold_cluster(env):
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web"):  # only 2 skills < global_skill_count=3
        capture(skill, "learning", body, "palette", "prov")

    result = compact(all_skills=True)
    assert result["promotions"] == []
    for skill in ("gt", "web"):
        assert len(load_learnings(store_location(skill))) == 1


def test_no_findings_removes_stale_report(env):
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    # Force a report to exist, then a clean compact should remove it.
    report = store_location("gt").path / "compact-report.md"
    report.write_text("stale", encoding="utf-8")

    result = compact("gt")
    assert result["findings"] == []
    assert result["report_path"] is None
    assert not report.exists()


def test_global_store_excluded_from_compact_all_scan(env):
    # Promote something so the global store exists, then ensure --all doesn't treat it as a skill.
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", "Prefer muted palettes.", "palette", "prov")
    compact(all_skills=True)  # creates + fills global store
    # A second --all must not re-scan/re-promote the global store's own entry.
    result = compact(all_skills=True)
    assert GLOBAL_SLUG not in result["skills"]
    assert result["promotions"] == []
