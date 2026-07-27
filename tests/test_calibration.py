"""M5b — the calibration harness: pure PRF math, the three KPIs, and the metrics fold-in.

These tests run against the light hashing backend (no ST/torch), so they assert exact scores only
where the result is embedding-independent (PRF set math, capture dedup) and shape/bounds elsewhere.
They skip when the harness's `pyyaml` dep is absent (fast CI job without the showcase extra).
"""

from __future__ import annotations

import json

import pytest

# The calibration harness is internal/command-only and lives under `harness/` (not the installed
# package), so it imports only when tests run from the repo root with its `pyyaml` dep present.
# importorskip keeps this module collectable everywhere — in CI's ST job (which imports every test
# module to collect, then runs only `-m embeddings`) it skips cleanly instead of erroring.
pytest.importorskip("yaml")
calibrate = pytest.importorskip("harness.calibrate")
hmetrics = pytest.importorskip("harness.metrics")


@pytest.fixture
def hashing_env(monkeypatch):
    # No ST pin — calibrate's _isolated_store supplies a throwaway store root per KPI.
    monkeypatch.setenv("WHETSTONE_EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("WHETSTONE_EMBEDDING_DIM", "256")


# --------------------------------------------------------------------------- pure PRF math


@pytest.mark.parametrize(
    "returned,relevant,expected",
    [
        ({"a"}, {"a"}, (1.0, 1.0, 1.0)),
        ({"a", "b"}, {"a"}, (0.5, 1.0)),  # precision 0.5, recall 1.0
        ({"a"}, {"a", "b"}, (1.0, 0.5)),  # precision 1.0, recall 0.5
        (set(), set(), (1.0, 1.0, 1.0)),  # nothing expected, nothing returned
        (set(), {"a"}, (0.0, 0.0, 0.0)),  # missed everything
    ],
)
def test_prf(returned, relevant, expected):
    p, r, f1 = calibrate._prf(returned, relevant)
    assert (round(p, 4), round(r, 4)) == expected[:2]
    if len(expected) == 3:
        assert round(f1, 4) == expected[2]


# --------------------------------------------------------------------------- the three KPIs


def test_capture_rate_counts_committed_and_reinforced(hashing_env):
    labels = calibrate.load_labels()
    result = calibrate.calibrate_capture(labels)
    # The labeled set has 4 correction turns; the two identical small-tables issues dedup to
    # committed + noop, so exactly 3 of 4 are captured (deterministic under hashing).
    assert result["n_corrections"] == 4
    assert result["captured"] == 3
    assert result["value"] == 0.75
    statuses = [d["status"] for d in result["detail"]]
    assert statuses == ["committed", "committed", "committed", "noop"]


def test_regressions_proxy_recalls_issue_in_scope(hashing_env):
    labels = calibrate.load_labels()
    result = calibrate.calibrate_regressions(labels)
    # Each case seeds one issue then recalls a violating intent; the low issues cutoff surfaces it.
    assert result["n_cases"] == 3
    assert result["value"] == 1.0
    assert all(d["recalled_in_scope"] for d in result["detail"])
    assert "proxy" in result["note"].lower()


def test_same_polarity_contradiction_scores_the_labeled_set(hashing_env):
    # §M7c: precision/recall of the antonym/negation same-polarity heuristic against its own
    # labeled section -- the scorer forces the config flag on and lowers dedup_similarity itself
    # (see calibrate_same_polarity_contradiction's docstring), so no extra env is needed here.
    labels = calibrate.load_labels()
    result = calibrate.calibrate_same_polarity_contradiction(labels)
    assert result["n_contradiction_pairs"] == 6
    assert result["n_duplicate_pairs"] == 6
    assert result["value"] == 1.0  # precision
    assert result["recall"] == 1.0
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 0
    assert result["not_reached"] == 0  # every labeled pair actually reached the heuristic
    assert "experimental" in result["note"].lower()


def test_retrieval_precision_shape_and_bounds(hashing_env):
    labels = calibrate.load_labels()
    result = calibrate.calibrate_retrieval(labels)
    assert result["n_cases"] == len(labels["retrieval_precision"]["cases"])
    assert 0.0 <= result["value"] <= 1.0
    for d in result["detail"]:
        assert set(d) >= {"intent", "returned_scopes", "relevant_scopes", "precision"}


def test_build_calibration_selects_single_kpi(hashing_env):
    labels = calibrate.load_labels()
    doc = calibrate.build_calibration(labels, "capture")
    assert "capture_rate" in doc
    assert "retrieval_precision" not in doc
    assert "regressions_prevented" not in doc


# --------------------------------------------------------------------------- metrics fold-in


def test_metrics_uses_null_fallback_when_calibration_absent(tmp_path):
    kpis = hmetrics._showcase_only_kpis(tmp_path / "calibration.json")
    for key in ("capture_rate", "regressions_prevented", "retrieval_precision"):
        assert kpis[key]["value"] is None
        assert kpis[key]["note"]
    assert "calibration_source" not in kpis


def test_metrics_uses_calibration_when_present(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "backend": "sentence-transformers",
                "generated_at": "2026-07-24T00:00:00Z",
                "labels": "harness/calibration/labels.yaml",
                "retrieval_precision": {"value": 0.91, "note": None},
                "capture_rate": {"value": 0.8, "note": None},
                "regressions_prevented": {"value": 0.7, "note": "proxy"},
            }
        ),
        encoding="utf-8",
    )
    kpis = hmetrics._showcase_only_kpis(path)
    assert kpis["retrieval_precision"]["value"] == 0.91
    assert kpis["capture_rate"]["value"] == 0.8
    assert kpis["regressions_prevented"]["value"] == 0.7
    assert kpis["calibration_source"]["backend"] == "sentence-transformers"
