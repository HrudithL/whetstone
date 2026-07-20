"""Aggregate the per-scenario summaries into the site's ``out/metrics.json``.

``python -m harness.metrics`` reads every ``out/<scenario>/summary.json`` the runner committed and
folds them into one ``out/metrics.json`` the dashboard reads. It is a pure aggregator of committed
data — it invents nothing. The two headline metrics come straight from the summaries:

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

_SHOWCASE_ONLY_NOTE = (
    "Not computed: the showcase seeds corrections via capture() directly against per-scenario "
    "isolated stores, so this labeled KPI has no honest denominator here. See runs_to_stick and "
    "value_over_time for the metrics this harness does measure."
)


def _load_summaries(out_root: Path) -> list[dict]:
    """Every ``out/<scenario>/summary.json``, sorted by scenario name."""
    summaries = []
    for path in sorted(out_root.glob("*/summary.json")):
        summaries.append(json.loads(path.read_text(encoding="utf-8")))
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


def build_metrics(out_root: Path = OUT_ROOT) -> dict:
    """Build the full ``metrics.json`` document from the committed per-scenario summaries."""
    summaries = _load_summaries(out_root)
    return {
        "backend": config.EMBEDDING_BACKEND,
        "generated_at": datetime.now(UTC).isoformat(),
        "scenarios": {s["scenario"]: s for s in summaries},
        "aggregate": _aggregate(summaries),
        "showcase_only_kpis": {
            "capture_rate": {"value": None, "note": _SHOWCASE_ONLY_NOTE},
            "regressions_prevented": {"value": None, "note": _SHOWCASE_ONLY_NOTE},
            "retrieval_precision": {"value": None, "note": _SHOWCASE_ONLY_NOTE},
        },
    }


def main() -> int:
    summaries = _load_summaries(OUT_ROOT)
    if not summaries:
        print(
            f"error: no out/<scenario>/summary.json under {OUT_ROOT} — run `python -m harness.run "
            "--agent` first",
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
