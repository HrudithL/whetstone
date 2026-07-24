"""Aggregate the per-scenario summaries into the site's ``out/metrics.json``.

``python -m harness.metrics`` reads every ``out/<skill>/<scenario>/summary.json`` the runner
committed and folds them into one ``out/metrics.json`` the dashboard reads. It is a pure aggregator
of committed data — it invents nothing. The two headline metrics come straight from the summaries:

* **runs-to-stick** — warm runs until a corrected preference is applied without re-correction.
* **value-over-time** — each learning's weight/recurrence trajectory across the warm runs.

Plus honest cross-scenario aggregates and the store's real usage KPIs (verbatim from each summary).
The three §11 *labeled* KPIs (capture_rate, regressions_prevented, retrieval_precision) stay
``null`` with a note: the showcase drives ``capture`` directly against per-scenario isolated stores,
so those cannot be computed honestly here — exactly as ``whetstone.metrics`` leaves them.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import config

OUT_ROOT = config.HARNESS_ROOT / "out"
CALIBRATION_PATH = OUT_ROOT / "calibration.json"

_SHOWCASE_ONLY_NOTE = (
    "Not computed here: the scenario runner seeds corrections via capture() directly against "
    "per-scenario isolated stores, so this labeled KPI has no honest denominator in the scenario "
    "pass. Run `python -m harness.calibrate` to compute it against the labeled set; see "
    "runs_to_stick and value_over_time for the metrics the scenario pass does measure."
)
# The three labeled KPIs the calibration harness (M5b) computes, keyed as in calibration.json.
_CALIBRATED_KPIS = ("capture_rate", "regressions_prevented", "retrieval_precision")


def _showcase_only_kpis(calibration_path: Path = CALIBRATION_PATH) -> dict:
    """The three labeled KPIs: real figures from ``calibration.json`` when present (M5b), else the
    honest null-with-note fallback (deterministic, key-free site build)."""
    calibration = {}
    if calibration_path.exists():
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    result = {}
    for kpi in _CALIBRATED_KPIS:
        if kpi in calibration:
            result[kpi] = calibration[kpi]
        else:
            result[kpi] = {"value": None, "note": _SHOWCASE_ONLY_NOTE}
    if calibration:
        result["calibration_source"] = {
            "backend": calibration.get("backend"),
            "generated_at": calibration.get("generated_at"),
            "labels": calibration.get("labels"),
        }
    return result


def _load_summaries(out_root: Path) -> list[dict]:
    """Every ``out/<skill>/<scenario>/summary.json``, sorted by (skill, scenario) path.

    The path is authoritative for the skill grouping — ``out/<skill>/<scenario>/`` is where the
    artifact physically lives — so the ``skill`` field is set from ``path.parent.parent.name``,
    back-filling any summary that predates the field.
    """
    summaries = []
    for path in sorted(out_root.glob("*/*/summary.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        s["skill"] = path.parent.parent.name
        summaries.append(s)
    return summaries


def _aggregate(summaries: list[dict]) -> dict:
    """Honest cross-scenario roll-up of the per-preference runs-to-stick facts."""
    total = wrong_cold = stuck = corrected_and_stuck = 0
    stick_counts: list[int] = []
    for s in summaries:
        for pref in s["preferences"].values():
            total += 1
            wrong = pref.get("cold_honored") is False
            rts = pref.get("runs_to_stick")
            if wrong:
                wrong_cold += 1
            if rts is not None:
                stuck += 1
                stick_counts.append(rts)
            if wrong and rts is not None:
                corrected_and_stuck += 1
    return {
        "scenarios": len(summaries),
        "preferences_total": total,
        "preferences_wrong_in_cold": wrong_cold,
        "preferences_stuck": stuck,
        "stuck_rate": round(stuck / total, 4) if total else None,
        "corrected_and_stuck": corrected_and_stuck,
        "median_runs_to_stick": statistics.median(stick_counts) if stick_counts else None,
    }


def _aggregate_by_skill(summaries: list[dict]) -> dict:
    """The same roll-up as :func:`_aggregate`, computed **per skill** (M4b groups by skill)."""
    by_skill: dict[str, list[dict]] = {}
    for s in summaries:
        by_skill.setdefault(s["skill"], []).append(s)
    return {skill: _aggregate(subset) for skill, subset in sorted(by_skill.items())}


def build_metrics(out_root: Path = OUT_ROOT) -> dict:
    """Build the full ``metrics.json`` document from the committed per-scenario summaries.

    ``scenarios`` stays keyed by scenario name (globally unique), so existing readers are unchanged;
    ``skills`` is the additive per-skill roll-up.
    """
    summaries = _load_summaries(out_root)
    return {
        "backend": config.EMBEDDING_BACKEND,
        "generated_at": datetime.now(UTC).isoformat(),
        "scenarios": {s["scenario"]: s for s in summaries},
        "skills": _aggregate_by_skill(summaries),
        "aggregate": _aggregate(summaries),
        "showcase_only_kpis": _showcase_only_kpis(out_root / "calibration.json"),
    }


def main() -> int:
    summaries = _load_summaries(OUT_ROOT)
    if not summaries:
        print(
            f"error: no out/<skill>/<scenario>/summary.json under {OUT_ROOT} — run "
            "`python -m harness.run --agent` first",
            file=sys.stderr,
        )
        return 1
    doc = build_metrics()
    (OUT_ROOT / "metrics.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    agg = doc["aggregate"]
    print(f"wrote {OUT_ROOT / 'metrics.json'}")
    print(
        f"  {agg['scenarios']} scenarios, {agg['preferences_total']} preferences; "
        f"{agg['preferences_stuck']} stuck (rate {agg['stuck_rate']}), "
        f"median runs-to-stick {agg['median_runs_to_stick']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
