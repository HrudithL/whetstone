"""KPI computation for the ``metrics`` tool (§11) — proving value from ordinary usage.

The headline proof is *usage telemetry*, not a benchmark. From a store's ``events.jsonl`` (plus the
current markdown state) this computes the KPIs that ordinary usage can support:

- **runs** — number of ``recall`` events.
- **avg learnings applied per run** — mean count of learnings returned per ``recall``.
- **capture counts by status** — ``committed`` / ``reinforced`` / ``noop``.
- **repeat-correction proxy** — the "money metric" (§11): the reinforcement rate (a repeated
  preference reinforced rather than newly captured) as a slowing-of-re-correction signal.
- **% survived** — learnings still present in the store vs. all ever created.

Three §11 KPIs need a known denominator or a labeled/calibration set and cannot be computed honestly
from ordinary usage — **capture-rate**, **regressions-prevented**, **retrieval-precision**. These
are *showcase-only* (§11/§12): each is returned as ``{"value": null, "note": ...}`` rather than
faked. The M3 showcase harness (scripted critiques, a calibration set, a blinded judge) computes
them.
"""

from __future__ import annotations

from .store.access import load_learnings
from .store.layout import StoreLocation
from .telemetry import read_events

# Notes returned for the showcase-only KPIs (§11/§12), so a dashboard shows *why* they are null.
_SHOWCASE_ONLY = {
    "capture_rate": (
        "Showcase-only (§11/§12): needs the denominator 'turns that contained a correction', "
        "which ordinary usage does not label. Computed by the M3 showcase harness (scripted "
        "critiques)."
    ),
    "regressions_prevented": (
        "Showcase-only (§11/§12): needs ground truth for 'a recalled issue was in scope and not "
        "reintroduced', which requires the M3 showcase harness."
    ),
    "retrieval_precision": (
        "Showcase-only (§11/§12): derived from embedding match scores against a labeled "
        "(elaborated-intent -> relevant-scopes) calibration set (M3), which ordinary usage lacks."
    ),
}


def _mean(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def compute_metrics(loc: StoreLocation) -> dict:
    """Compute the §11 KPIs for one store from its event log and current markdown state."""
    events = read_events(loc)
    recalls = [e for e in events if e.get("type") == "recall"]
    captures = [e for e in events if e.get("type") == "capture"]

    learnings_per_run = [int(e.get("counts", {}).get("learnings", 0)) for e in recalls]

    by_status = {"committed": 0, "reinforced": 0, "noop": 0}
    for e in captures:
        status = e.get("status")
        if status in by_status:
            by_status[status] += 1

    # Repeat-correction proxy (§11): among learning-directed captures, how often a preference was
    # *reinforced* (already known) rather than newly *committed*. A rising rate = re-corrections
    # increasingly land on existing learnings, i.e. recurrence growth rather than new entries.
    learning_committed = sum(
        1 for e in captures if e.get("status") == "committed" and e.get("polarity") == "learning"
    )
    reinforcements = by_status["reinforced"]
    reinforce_denom = learning_committed + reinforcements
    reinforcement_rate = (
        round(reinforcements / reinforce_denom, 4) if reinforce_denom else None
    )

    # % survived: learnings still present vs. all ever created. Created = committed learning
    # captures (reinforcements touch an existing entry, they don't create one). Removal lands in
    # M2b's revise/compaction, so today this is ~100% wherever any learning was created; it is wired
    # now so the KPI goes live the moment removals exist.
    #
    # This is only honest when telemetry covers every learning currently in the store. If the store
    # holds learnings the event log never recorded creating (a pre-telemetry or manually-imported
    # store — so present > created, or present>0 with no logged creations), the denominator is
    # incomplete: report unknown rather than a >100% or otherwise misleading figure.
    present_learnings = len(load_learnings(loc))
    if learning_committed and present_learnings <= learning_committed:
        survived_pct = {
            "value": round(present_learnings / learning_committed, 4),
            "note": None,
        }
    else:
        survived_pct = {
            "value": None,
            "note": (
                "Incomplete telemetry coverage: the store has learnings not represented by "
                "committed capture events (pre-telemetry or imported markdown), so % survived "
                "cannot be computed honestly from the event log."
            ),
        }

    return {
        "runs": len(recalls),
        "avg_learnings_applied_per_run": _mean(learnings_per_run),
        "captures_by_status": by_status,
        "repeat_correction_proxy": {
            "reinforcement_rate": reinforcement_rate,
            "reinforcements": reinforcements,
            "learnings_created": learning_committed,
        },
        "learnings_survived_pct": survived_pct,
        # Showcase-only KPIs (§11/§12) — never faked; see module docstring.
        "capture_rate": {"value": None, "note": _SHOWCASE_ONLY["capture_rate"]},
        "regressions_prevented": {
            "value": None,
            "note": _SHOWCASE_ONLY["regressions_prevented"],
        },
        "retrieval_precision": {
            "value": None,
            "note": _SHOWCASE_ONLY["retrieval_precision"],
        },
    }
