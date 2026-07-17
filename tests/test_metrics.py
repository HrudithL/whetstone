"""Tests for the §11 KPI computation and the ``metrics`` tool.

Feasible KPIs are computed on a fixture event log; the three showcase-only KPIs must come back as
``{"value": null, "note": ...}`` — never faked.
"""

from __future__ import annotations

from whetstone.metrics import compute_metrics
from whetstone.server import capture, metrics, recall
from whetstone.telemetry import append_event


def _seed_events(loc, events):
    for e in events:
        append_event(loc, e)


def test_feasible_kpis_on_a_fixture_log(store, config):
    # One committed learning (L1), later reinforced; plus one committed issue (I1). Two recall runs
    # returning 2 and 4 learnings.
    from conftest import make_learning
    from whetstone.store.access import save_learning

    save_learning(store, make_learning("L1", "Right-align currency columns.", "currency"))

    def rec(run_id, n_learn, n_issue):
        return {"type": "recall", "run_id": run_id, "intent": "i",
                "counts": {"learnings": n_learn, "issues": n_issue}}

    def cap(run_id, entry_id, polarity, status):
        return {"type": "capture", "run_id": run_id, "entry_id": entry_id,
                "polarity": polarity, "status": status}

    _seed_events(
        store,
        [
            rec("r1", 2, 1),
            rec("r2", 4, 0),
            cap("r1", "L1", "learning", "committed"),
            cap("r2", "L1", "learning", "reinforced"),
            cap("r2", "I1", "issue", "committed"),
            cap("r2", "I1", "issue", "noop"),
        ],
    )

    m = compute_metrics(store)
    assert m["runs"] == 2
    assert m["avg_learnings_applied_per_run"] == 3.0  # mean of 2 and 4
    assert m["captures_by_status"] == {"committed": 2, "reinforced": 1, "noop": 1, "conflict": 0}
    # reinforcement_rate = reinforced / (learning_committed + reinforced) = 1 / (1 + 1) = 0.5
    assert m["repeat_correction_proxy"]["reinforcement_rate"] == 0.5
    assert m["repeat_correction_proxy"]["reinforcements"] == 1
    assert m["repeat_correction_proxy"]["learnings_created"] == 1
    # One learning created, one still present -> 100% survived.
    assert m["learnings_survived_pct"]["value"] == 1.0


def test_showcase_only_kpis_are_null_with_a_note(store):
    m = compute_metrics(store)
    for key in ("capture_rate", "regressions_prevented", "retrieval_precision"):
        assert m[key]["value"] is None
        assert "howcase" in m[key]["note"]  # note explains it is showcase-only


def test_empty_store_metrics(store):
    m = compute_metrics(store)
    assert m["runs"] == 0
    assert m["avg_learnings_applied_per_run"] is None
    assert m["captures_by_status"] == {"committed": 0, "reinforced": 0, "noop": 0, "conflict": 0}
    assert m["repeat_correction_proxy"]["reinforcement_rate"] is None
    assert m["learnings_survived_pct"]["value"] is None


def test_metrics_tool_for_one_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    recall("gt", "styling a table")
    capture("gt", "learning", "Prefer muted palettes.", "color", "prov")

    report = metrics("gt")
    assert report["skill"] == "gt"
    assert report["runs"] == 1
    assert report["captures_by_status"]["committed"] == 1
    assert report["learnings_survived_pct"]["value"] == 1.0
    assert report["capture_rate"]["value"] is None


def test_metrics_tool_all_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    recall("gt", "styling a table")
    recall("code-review", "reviewing a diff")
    capture("code-review", "issue", "Never ignore failing tests.", "tests", "prov")

    report = metrics()
    assert set(report["skills"]) == {"gt", "code-review"}
    assert report["skills"]["gt"]["runs"] == 1
    assert report["skills"]["code-review"]["captures_by_status"]["committed"] == 1


def test_survived_pct_unknown_when_telemetry_coverage_incomplete(tmp_path, monkeypatch):
    # A store with learnings not represented by committed capture events (e.g. imported markdown)
    # must report % survived as unknown, never a >100% figure.
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    # Two real learnings in the store, but no capture events recorded their creation.
    capture("gt", "learning", "Prefer muted palettes.", "color", "prov")
    capture("gt", "learning", "Right-align currency.", "currency", "prov")
    from whetstone.store.layout import store_location
    from whetstone.telemetry import events_path

    events_path(store_location("gt")).unlink()  # wipe telemetry -> present(2) > committed(0)

    report = metrics("gt")
    assert report["learnings_survived_pct"]["value"] is None
    assert "ncomplete" in report["learnings_survived_pct"]["note"]


def test_revise_reinforcements_count_in_the_repeat_metric(store, config):
    # Reinforcements now usually arrive via revise(action=reinforce), not capture; they must feed
    # the repeat-correction proxy alongside capture 'reinforced' events.
    from conftest import make_learning
    from whetstone.store.access import save_learning

    save_learning(store, make_learning("L1", "Right-align currency.", "currency"))
    _seed_events(
        store,
        [
            {"type": "capture", "run_id": "r1", "entry_id": "L1",
             "polarity": "learning", "status": "committed"},
            {"type": "revise", "run_id": "r2", "entry_id": "L1",
             "action": "reinforce", "status": "reinforced"},
            {"type": "revise", "run_id": "r3", "entry_id": "L1",
             "action": "reinforce", "status": "reinforced"},
        ],
    )
    m = compute_metrics(store)
    # 2 revise reinforcements, 1 capture-committed learning -> 2 / (1 + 2) = 0.6667.
    assert m["repeat_correction_proxy"]["reinforcements"] == 2
    assert m["repeat_correction_proxy"]["reinforcement_rate"] == round(2 / 3, 4)


def test_conflict_captures_are_counted_by_status(store, config):
    # capture now emits status "conflict" when a new entry clashes with an opposite-polarity rule;
    # those events must be tallied, not silently dropped.
    _seed_events(
        store,
        [
            {"type": "capture", "run_id": "r1", "entry_id": "L1",
             "polarity": "learning", "status": "committed"},
            {"type": "capture", "run_id": "r2", "entry_id": "I1",
             "polarity": "learning", "status": "conflict"},
            {"type": "capture", "run_id": "r3", "entry_id": "L1",
             "polarity": "issue", "status": "conflict"},
        ],
    )
    m = compute_metrics(store)
    assert m["captures_by_status"]["conflict"] == 2


def test_demoted_learning_counts_as_a_creation_for_survival(store, config):
    # A revise demote mints a new learning (L2 from an issue). It is a "created" learning, so a
    # store holding only that learning should report 100% survived, not 'incomplete coverage'.
    from conftest import make_learning
    from whetstone.store.access import save_learning

    save_learning(store, make_learning("L2", "Prefer avoiding neon.", "color"))
    _seed_events(
        store,
        [
            {"type": "revise", "run_id": "r1", "entry_id": "L2",
             "action": "demote", "status": "demoted"},
        ],
    )
    m = compute_metrics(store)
    assert m["learnings_survived_pct"]["value"] == 1.0


def test_survived_pct_unknown_when_a_learning_id_is_reused(store):
    # If a learning id appears in two creation events (removed, then id reused), the set-based
    # coverage check would collapse them; survival must be reported as unknown instead.
    from conftest import make_learning
    from whetstone.store.access import save_learning

    save_learning(store, make_learning("L1", "Right-align currency.", "currency"))
    _seed_events(
        store,
        [
            {"type": "capture", "run_id": "r1", "entry_id": "L1",
             "polarity": "learning", "status": "committed"},
            {"type": "capture", "run_id": "r2", "entry_id": "L1",
             "polarity": "learning", "status": "committed"},
        ],
    )
    m = compute_metrics(store)
    assert m["learnings_survived_pct"]["value"] is None
    assert "reused" in m["learnings_survived_pct"]["note"]
