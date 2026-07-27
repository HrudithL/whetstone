"""M5b — the calibration harness: compute the three labeled §11 KPIs for the showcase.

``python -m harness.calibrate [--kpi retrieval|capture|regressions|all]``

The product ``metrics`` MCP tool returns ``null`` for ``capture_rate``, ``regressions_prevented``,
and ``retrieval_precision`` *by design* — ordinary runtime usage has no labeled ground truth. This
internal, command-only harness supplies exactly that missing piece: a small **hand-labeled set**
(``calibration/labels.yaml``) it scores against **real Whetstone** to produce honest numbers for the
*published showcase*. It writes ``out/calibration.json``; :mod:`harness.metrics` folds it into
``out/metrics.json``, and the site shows real figures where it used to show null-with-note.

**Hard boundary (keeps the honesty story intact):** the runtime ``metrics`` tool STILL returns null
for these three — nothing here changes that. Only the published showcase, linked to this labeled set
and runner, shows calibrated aggregates. This mirrors the M3 showcase-harness-is-internal boundary.

The three KPIs, their labels, and cost:

- **retrieval_precision** — labels: ``(intent -> relevant scope set)``. Seed a store, run
  ``recall``, score returned scopes against the labels (precision/recall/F1). **No API key.**
- **capture_rate** — labels: correction turns. Drive ``capture`` per turn; a turn counts as
  captured when the result is ``committed``/``reinforced`` (not ``noop``/``conflict``). **No key.**
- **regressions_prevented** — labels: ``(in-scope issue, a violating intent)``. The key-free
  **proxy** verifies the issue is recalled in-scope for the violating intent (so the model is warned
  before it can regress). A live ``--agent`` cold-vs-warm variant is the published number; the proxy
  stands in for key-free local dev.

All KPIs run against ephemeral, isolated stores with the global layer OFF, so the numbers reflect
per-skill retrieval only and never touch a real user store.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import yaml

from . import config as hconfig

CALIBRATION_DIR = hconfig.HARNESS_ROOT / "calibration"
LABELS_PATH = CALIBRATION_DIR / "labels.yaml"
OUT_PATH = hconfig.HARNESS_ROOT / "out" / "calibration.json"

_SKILL = "calibration"
_REGRESSION_PROXY_NOTE = (
    "Key-free proxy: verifies the in-scope issue was recalled for a violating intent (not a live "
    "generation). The published figure uses the --agent cold-vs-warm variant."
)


def load_labels(path: Path = LABELS_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _prf(returned, relevant) -> tuple[float, float, float]:
    """Precision, recall, F1 of a returned set against the relevant set (pure set math)."""
    returned, relevant = set(returned), set(relevant)
    if not returned and not relevant:
        return 1.0, 1.0, 1.0
    hits = len(returned & relevant)
    precision = hits / len(returned) if returned else 0.0
    recall = hits / len(relevant) if relevant else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


@contextmanager
def _isolated_store():
    """A throwaway store root with the global layer OFF, so each KPI scores in isolation.

    Overrides only ``WHETSTONE_STORE_ROOT`` + ``WHETSTONE_CONSULT_GLOBAL`` (the embedding backend is
    whatever the caller pinned — ST via :func:`harness.config.apply_showcase_env` in ``main``, or
    ``hashing`` in tests). Restores prior env on exit.
    """
    keys = ("WHETSTONE_STORE_ROOT", "WHETSTONE_CONSULT_GLOBAL")
    saved = {k: os.environ.get(k) for k in keys}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["WHETSTONE_STORE_ROOT"] = tmp
        os.environ["WHETSTONE_CONSULT_GLOBAL"] = "false"
        try:
            yield
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def calibrate_retrieval(labels: dict) -> dict:
    """retrieval_precision: seed a store, recall each labeled intent, score returned scopes."""
    from whetstone.server import capture, recall

    spec = labels["retrieval_precision"]
    precisions, recalls, f1s, detail = [], [], [], []
    with _isolated_store():
        for e in spec["entries"]:
            capture(_SKILL, e["polarity"], e["body"], e["scope"], "calibration")
        for case in spec["cases"]:
            res = recall(_SKILL, case["intent"])
            returned = {x["scope"] for x in res["learnings"] + res["issues"]}
            p, r, f1 = _prf(returned, case["relevant"])
            precisions.append(p)
            recalls.append(r)
            f1s.append(f1)
            detail.append(
                {
                    "intent": case["intent"],
                    "returned_scopes": sorted(returned),
                    "relevant_scopes": sorted(case["relevant"]),
                    "precision": round(p, 4),
                    "recall": round(r, 4),
                    "f1": round(f1, 4),
                }
            )
    return {
        "value": round(statistics.mean(precisions), 4) if precisions else None,
        "recall": round(statistics.mean(recalls), 4) if recalls else None,
        "f1": round(statistics.mean(f1s), 4) if f1s else None,
        "n_cases": len(detail),
        "note": None,
        "detail": detail,
    }


def calibrate_capture(labels: dict) -> dict:
    """capture_rate: drive capture per correction turn; captured = committed | reinforced."""
    from whetstone.server import capture

    turns = [t for t in labels["capture_rate"]["turns"] if t.get("contains_correction", True)]
    captured, detail = 0, []
    with _isolated_store():
        for t in turns:
            res = capture(_SKILL, t["polarity"], t["body"], t["scope"], "calibration")
            ok = res.get("status") in ("committed", "reinforced")
            captured += int(ok)
            detail.append({"scope": t["scope"], "status": res.get("status"), "captured": ok})
    return {
        "value": round(captured / len(turns), 4) if turns else None,
        "n_corrections": len(turns),
        "captured": captured,
        "note": None,
        "detail": detail,
    }


def calibrate_regressions(labels: dict) -> dict:
    """regressions_prevented (key-free proxy): in-scope issue is recalled for a violating intent."""
    from whetstone.server import capture, recall

    cases = labels["regressions_prevented"]["cases"]
    prevented, detail = 0, []
    for case in cases:
        with _isolated_store():  # one issue per store, so cases never cross-contaminate
            issue = case["issue"]
            capture(_SKILL, "issue", issue["body"], issue["scope"], "calibration")
            res = recall(_SKILL, case["intent"])
            surfaced = any(x["scope"] == issue["scope"] for x in res["issues"])
            prevented += int(surfaced)
            detail.append(
                {
                    "intent": case["intent"],
                    "issue_scope": issue["scope"],
                    "recalled_in_scope": surfaced,
                }
            )
    return {
        "value": round(prevented / len(cases), 4) if cases else None,
        "n_cases": len(cases),
        "prevented": prevented,
        "note": _REGRESSION_PROXY_NOTE,
        "detail": detail,
    }


def calibrate_same_polarity_contradiction(labels: dict) -> dict:
    """same_polarity_contradiction (§M7c, experimental): precision/recall of the antonym/negation
    same-polarity heuristic, scored against ``labels.yaml``'s hand-labeled contradiction/duplicate
    pairs.

    For each ``contradiction_pairs`` case, seed ``first`` then ``capture`` ``second`` in the same
    scope -- the heuristic SHOULD return ``possible_contradiction`` (a true positive; a silent
    ``reinforced`` here is a false negative, a miss). For each ``duplicate_pairs`` case (including
    the deliberately tricky near-misses that mention the same antonym/negation words on both sides),
    the same drive SHOULD reinforce normally -- a ``possible_contradiction`` here is a false
    positive.

    Forces ``same_polarity_contradiction_check`` on and lowers ``dedup_similarity`` for the duration
    of this measurement, regardless of the shipped config default or which embedding backend is
    active: the heuristic only ever runs once ``_find_duplicate`` has already flagged a pair as a
    near-duplicate, and this KPI measures the heuristic ALONE, not whether ``dedup_similarity``
    itself reliably catches these hand-written pairs on every backend (the hashing backend, in
    particular, scores single-word-substituted antonym pairs anywhere from ~0.71 to ~0.94 -- see the
    pairs in ``labels.yaml`` -- so a fixed, generous override keeps this KPI's set stable across the
    fast hashing job and the sentence-transformers job alike).
    """
    from whetstone.server import capture

    spec = labels["same_polarity_contradiction"]
    tp = fn = tn = fp = 0
    detail = []
    keys = ("WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK", "WHETSTONE_DEDUP_SIMILARITY")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ["WHETSTONE_SAME_POLARITY_CONTRADICTION_CHECK"] = "true"
    os.environ["WHETSTONE_DEDUP_SIMILARITY"] = "0.6"
    try:
        for case in spec.get("contradiction_pairs", []):
            with _isolated_store():
                capture(_SKILL, "learning", case["first"], case["scope"], "calibration")
                res = capture(_SKILL, "learning", case["second"], case["scope"], "calibration")
                fired = res.get("status") == "possible_contradiction"
                tp += int(fired)
                fn += int(not fired)
                detail.append(
                    {
                        "scope": case["scope"],
                        "kind": "contradiction",
                        "status": res.get("status"),
                        "correct": fired,
                    }
                )
        for case in spec.get("duplicate_pairs", []):
            with _isolated_store():
                capture(_SKILL, "learning", case["first"], case["scope"], "calibration")
                res = capture(_SKILL, "learning", case["second"], case["scope"], "calibration")
                fired = res.get("status") == "possible_contradiction"
                tn += int(not fired)
                fp += int(fired)
                detail.append(
                    {
                        "scope": case["scope"],
                        "kind": "duplicate",
                        "status": res.get("status"),
                        "correct": not fired,
                    }
                )
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {
        "value": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "n_contradiction_pairs": tp + fn,
        "n_duplicate_pairs": tn + fp,
        "true_positives": tp,
        "false_negatives": fn,
        "true_negatives": tn,
        "false_positives": fp,
        "note": (
            "Experimental (§M7c spike): a small, non-exhaustive antonym/negation lexicon flags a "
            "same-scope near-duplicate learning pair as `possible_contradiction` instead of "
            "silently reinforcing. `value` is precision over fired flags; `recall` is the fraction "
            "of labeled contradiction pairs caught. Measured with the config flag forced ON "
            "regardless of its shipped default -- see config.py's "
            "`same_polarity_contradiction_check`."
        ),
        "detail": detail,
    }


_KPIS = {
    "retrieval": ("retrieval_precision", calibrate_retrieval),
    "capture": ("capture_rate", calibrate_capture),
    "regressions": ("regressions_prevented", calibrate_regressions),
    "same_polarity": ("same_polarity_contradiction", calibrate_same_polarity_contradiction),
}


def build_calibration(labels: dict, kpi: str = "all") -> dict:
    """Compute the requested KPI(s) into the ``calibration.json`` document."""
    doc = {
        "backend": os.environ.get("WHETSTONE_EMBEDDING_BACKEND", "hashing"),
        "generated_at": datetime.now(UTC).isoformat(),
        "labels": str(LABELS_PATH.relative_to(hconfig.HARNESS_ROOT.parent)),
    }
    for key, (out_key, fn) in _KPIS.items():
        if kpi in (key, "all"):
            doc[out_key] = fn(labels)
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute the labeled §11 KPIs for the showcase.")
    parser.add_argument("--kpi", choices=[*_KPIS, "all"], default="all")
    parser.add_argument("--out", default=str(OUT_PATH), help="output JSON path")
    args = parser.parse_args(argv)

    # Pin the ST backend + isolated XDG config exactly like the rest of the harness, so the
    # published numbers use the calibrated thresholds. (Each KPI still overrides the store root.)
    hconfig.apply_showcase_env()
    labels = load_labels()
    doc = build_calibration(labels, args.kpi)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    for out_key, _ in _KPIS.values():
        if out_key in doc:
            print(f"  {out_key}: {doc[out_key]['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
