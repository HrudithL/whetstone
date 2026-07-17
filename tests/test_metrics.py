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
    assert m["captures_by_status"] == {"committed": 2, "reinforced": 1, "noop": 1}
    # reinforcement_rate = reinforced / (learning_committed + reinforced) = 1 / (1 + 1) = 0.5
    assert m["repeat_correction_proxy"]["reinforcement_rate"] == 0.5
    assert m["repeat_correction_proxy"]["reinforcements"] == 1
    assert m["repeat_correction_proxy"]["learnings_created"] == 1
    # One learning created, one still present -> 100% survived.
    assert m["learnings_survived_pct"] == 1.0


def test_showcase_only_kpis_are_null_with_a_note(store):
    m = compute_metrics(store)
    for key in ("capture_rate", "regressions_prevented", "retrieval_precision"):
        assert m[key]["value"] is None
        assert "howcase" in m[key]["note"]  # note explains it is showcase-only


def test_empty_store_metrics(store):
    m = compute_metrics(store)
    assert m["runs"] == 0
    assert m["avg_learnings_applied_per_run"] is None
    assert m["captures_by_status"] == {"committed": 0, "reinforced": 0, "noop": 0}
    assert m["repeat_correction_proxy"]["reinforcement_rate"] is None
    assert m["learnings_survived_pct"] is None


def test_metrics_tool_for_one_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    recall("gt", "styling a table")
    capture("gt", "learning", "Prefer muted palettes.", "color", "prov")

    report = metrics("gt")
    assert report["skill"] == "gt"
    assert report["runs"] == 1
    assert report["captures_by_status"]["committed"] == 1
    assert report["learnings_survived_pct"] == 1.0
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
