"""M5a — behavioral mining folded into compact: the four advisory rules, the report, and --all.

§M7a: ``compact --all``'s cross-skill promotion is advisory-only — it reports ``global_candidate``
findings and never writes; enacting one is :func:`whetstone.promotion.promote_cluster` (also
reachable via ``whetstone promote <skill> <id> --cluster``, see the CLI test near the bottom)."""

from __future__ import annotations

import json
import shlex
from datetime import date

import pytest

from conftest import make_learning, seed
from whetstone.compaction import compact
from whetstone.config import Config
from whetstone.promotion import promote_cluster
from whetstone.server import capture, recall, revise
from whetstone.server import main as cli_main
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


def test_conflict_residue_ignores_a_revise_that_happened_before_it(env):
    # §round-5 Codex review finding: a revise BEFORE a later, still-unresolved conflict must NOT be
    # treated as having resolved it -- only a revise AFTER a conflict/contradiction event counts.
    capture("gt", "learning", "Prefer bright neon palettes.", "palette", "prov")
    revise("gt", "L1", "reinforce")  # resolves nothing yet -- there's no pending conflict
    _emit_conflict(store_location("gt"), "L1")  # NOW a conflict arrives, unresolved since

    residue = [f for f in compact("gt")["findings"] if f["rule"] == "conflict_residue"]
    assert len(residue) == 1
    assert residue[0]["id"] == "L1"


def test_possible_contradiction_residue_flagged(env, monkeypatch):
    # §M7c: an unresolved `possible_contradiction` (same-polarity, signal-only) must also surface as
    # residue -- it writes nothing, just like `conflict`, so without this a real, still-blocking
    # contradiction would never show up in a compact report.
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")
    monkeypatch.setenv("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "true")
    capture(
        "gt", "learning", "Right-align currency columns for a cleaner ledger look.", "palette",
        "prov",
    )
    capture(
        "gt", "learning", "Left-align currency columns for a cleaner ledger look.", "palette",
        "prov",
    )

    residue = [f for f in compact("gt")["findings"] if f["rule"] == "conflict_residue"]
    assert len(residue) == 1
    assert residue[0]["id"] == "L1"
    # §round-6 Codex review finding: the persisted candidate_body/note must be surfaced in the
    # finding's evidence, not just live on the underlying event -- otherwise an operator viewing the
    # report still can't see what actually opposed the flagged entry.
    assert residue[0]["evidence"]["candidate_body"] == (
        "Left-align currency columns for a cleaner ledger look."
    )
    assert residue[0]["evidence"]["note"]


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


# ------------------------------------------------------ compact --all: advisory-only (§M7a)


def test_compact_all_reports_candidate_without_writing(env):
    """§M7a: `compact --all` only ever detects + reports a cross-skill cluster — it must never
    write to the global store or retire any per-skill copy itself."""
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", body, "palette", "prov")

    result = compact(all_skills=True)

    assert result["all"] is True
    candidates = result["global_candidates"]
    assert len(candidates) == 1
    finding = candidates[0]
    assert finding["rule"] == "global_candidate"
    assert set(finding["skills"]) == {"gt", "web", "ppt"}
    rep = finding["representative"]
    assert rep["skill"] in {"gt", "web", "ppt"}
    assert finding["enact"] == f"whetstone promote {rep['skill']} {rep['id']} --cluster"

    # Nothing was written or retired — every per-skill copy is untouched, and the global store was
    # never even created.
    for skill in ("gt", "web", "ppt"):
        assert len(load_learnings(store_location(skill))) == 1
    assert not global_store_location(Config(store_root=env, embedding_dim=384)).path.exists()


def test_compact_all_ignores_below_threshold_cluster(env):
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web"):  # only 2 skills < global_skill_count=3
        capture(skill, "learning", body, "palette", "prov")

    result = compact(all_skills=True)
    assert result["global_candidates"] == []
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
    # Enact a reported candidate by hand so the global store exists, then ensure a later --all
    # doesn't treat it as a skill (and, with the source cluster now retired, has nothing left to
    # re-report).
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", "Prefer muted palettes.", "palette", "prov")
    finding = compact(all_skills=True)["global_candidates"][0]
    rep = finding["representative"]
    promote_cluster(rep["skill"], rep["id"])

    result = compact(all_skills=True)
    assert GLOBAL_SLUG not in result["skills"]
    assert result["global_candidates"] == []


# --------------------------------------------------------- promote_cluster: the enact path (§M7a)


def test_promote_cluster_enacts_a_reported_candidate(env):
    """`promote_cluster` performs exactly the write `compact --all` used to do automatically: the
    representative lands in the global store under a re-minted id, and every cluster member across
    all its skills is retired."""
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", body, "palette", "prov")

    finding = compact(all_skills=True)["global_candidates"][0]
    rep = finding["representative"]

    out = promote_cluster(rep["skill"], rep["id"])

    assert out["global_id"].startswith("L")
    assert set(out["skills"]) == {"gt", "web", "ppt"}
    assert {r["skill"] for r in out["retired"]} == {"gt", "web", "ppt"}
    for skill in ("gt", "web", "ppt"):
        assert load_learnings(store_location(skill)) == []
    g_learnings = load_learnings(global_store_location(Config(store_root=env, embedding_dim=384)))
    assert len(g_learnings) == 1
    assert g_learnings[0].id == out["global_id"]
    assert "muted" in g_learnings[0].body


def test_promote_cluster_unknown_entry_raises(env):
    with pytest.raises(ValueError, match="no cross-skill cluster"):
        promote_cluster("gt", "L999")


def test_promote_cluster_rejects_non_representative_member(env):
    """Regression: `<skill> <id>` must actually BE the cluster's current representative, not just
    any member — passing an arbitrary member id must not silently promote the cluster using
    whatever entry happens to be the real representative instead."""
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", body, "palette", "prov")

    finding = compact(all_skills=True)["global_candidates"][0]
    rep = finding["representative"]
    other = next(
        m
        for m in finding["evidence"]["members"]
        if (m["skill"], m["id"]) != (rep["skill"], rep["id"])
    )

    with pytest.raises(ValueError, match="not its current representative"):
        promote_cluster(other["skill"], other["id"])

    # Nothing was written or retired (the global store directory may exist from `ensure_store`,
    # but it must hold no entries).
    assert load_learnings(global_store_location(Config(store_root=env, embedding_dim=384))) == []
    for skill in ("gt", "web", "ppt"):
        assert len(load_learnings(store_location(skill))) == 1


def test_promote_cluster_revalidates_under_lock_against_stale_detection(env, monkeypatch):
    """Regression for a Codex-flagged race: `find_cross_skill_clusters` runs unlocked, so two
    concurrent `promote_cluster` calls for the same finding could both pass their own unlocked
    fast-fail check before either takes the global lock. The lock must serialize them so the
    second (losing) call's *locked* re-detection sees the post-promotion state and raises, instead
    of trusting its earlier unlocked snapshot and writing a stale duplicate.

    A real race needs two threads; this simulates the same interleaving in one thread by making
    the "losing" call's first (unlocked) detection return a snapshot taken before a "winning" call
    runs to completion in between — exactly what an actual concurrent winner would have produced —
    while its second (locked) detection call goes through to the real, now up-to-date store state.
    """
    import whetstone.compaction as compaction_mod

    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", body, "palette", "prov")

    finding = compact(all_skills=True)["global_candidates"][0]
    rep = finding["representative"]

    real_detect = compaction_mod.find_cross_skill_clusters
    calls = {"n": 0}

    def racing_detect(config, backend, skills=None):
        calls["n"] += 1
        if calls["n"] == 1:
            # This is the losing call's own unlocked fast-check. Capture what it would genuinely
            # see right now (the cluster still intact), THEN let a concurrent winner run to
            # completion — as it would during the real race window — before returning that
            # earlier snapshot, simulating the losing call having read it just before the winner.
            snapshot = real_detect(config, backend, skills=skills)
            promote_cluster(rep["skill"], rep["id"])  # the "winning" concurrent caller
            return snapshot
        return real_detect(config, backend, skills=skills)  # the losing call's locked recheck

    monkeypatch.setattr(compaction_mod, "find_cross_skill_clusters", racing_detect)

    with pytest.raises(ValueError, match="no cross-skill cluster"):
        promote_cluster(rep["skill"], rep["id"])  # the "losing" concurrent caller

    g_learnings = load_learnings(global_store_location(Config(store_root=env, embedding_dim=384)))
    assert len(g_learnings) == 1  # only the winner's write landed — no stale duplicate


def test_promote_cluster_revalidates_real_membership_not_just_id_existence(env):
    """Regression: a member that was *revised* (not removed) in the gap between a finding being
    reported and it being enacted must drop the cluster below threshold and abort the whole
    promotion — an existence-only check (the id still resolves to something) would wrongly let it
    through despite it no longer actually matching the cluster."""
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", body, "palette", "prov")

    finding = compact(all_skills=True)["global_candidates"][0]
    rep = finding["representative"]

    # Reword one non-representative member to something unrelated: it still exists (same id), but
    # no longer clusters with the other two — as if a `revise` landed on it after the finding was
    # reported but before it was enacted.
    member = next(m for m in finding["evidence"]["members"] if m["skill"] != rep["skill"])
    revise(
        member["skill"],
        member["id"],
        "reinforce",
        body="Completely unrelated database migration notes.",
    )

    with pytest.raises(ValueError, match="no cross-skill cluster"):
        promote_cluster(rep["skill"], rep["id"])

    # Nothing was written or retired — the whole cluster is now below global_skill_count.
    assert not global_store_location(Config(store_root=env, embedding_dim=384)).path.exists()
    for skill in ("gt", "web", "ppt"):
        assert len(load_learnings(store_location(skill))) == 1


def test_cli_promote_preserves_skill_literally_named_dashdash_cluster(env, capsys):
    """Regression: `--cluster` is a flag only in its fixed trailing slot. A skill genuinely named
    `--cluster` (skill names are otherwise unrestricted text) must still parse as a normal
    positional `skill` for the single-entry `promote <skill> <id>` shape."""
    res = capture("--cluster", "learning", "Prefer muted palettes.", "palette", "prov")
    entry_id = res["entry_id"]

    cli_main(["promote", "--cluster", entry_id])

    out = json.loads(capsys.readouterr().out)
    assert out["skill"] == "--cluster"
    assert out["source_id"] == entry_id
    assert load_learnings(store_location("--cluster")) == []


def test_cli_promote_cluster_flag_enacts_candidate(env, capsys):
    """The exact CLI invocation a `global_candidate` finding's ``enact`` string names."""
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("gt", "web", "ppt"):
        capture(skill, "learning", body, "palette", "prov")
    finding = compact(all_skills=True)["global_candidates"][0]
    rep = finding["representative"]

    cli_main(["promote", rep["skill"], rep["id"], "--cluster"])

    out = json.loads(capsys.readouterr().out)
    assert out["global_id"].startswith("L")
    for skill in ("gt", "web", "ppt"):
        assert load_learnings(store_location(skill)) == []


def test_global_candidate_enact_command_is_shell_safe_for_skill_with_spaces(env, capsys):
    """Regression: a skill name containing whitespace must not turn `enact` into a command whose
    positional args a shell (or `server.main`'s own splitting) would parse as extra tokens."""
    body = "Prefer muted, low-saturation color palettes."
    for skill in ("great tables", "web app", "ppt deck"):
        capture(skill, "learning", body, "palette", "prov")

    finding = compact(all_skills=True)["global_candidates"][0]
    rep = finding["representative"]
    assert " " in rep["skill"]  # the representative itself has a space, exercising the fix

    # shlex.split must reproduce exactly the 5 intended tokens, not split the skill name apart.
    tokens = shlex.split(finding["enact"])
    assert tokens == ["whetstone", "promote", rep["skill"], rep["id"], "--cluster"]

    # And feeding those parsed tokens to the CLI (as a real shell would after parsing the pasted
    # command) actually enacts the candidate.
    cli_main(tokens[1:])
    out = json.loads(capsys.readouterr().out)
    assert out["global_id"].startswith("L")
    for skill in ("great tables", "web app", "ppt deck"):
        assert load_learnings(store_location(skill)) == []
