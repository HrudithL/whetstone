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
from .store.layout import StoreLocation, store_write_lock
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
    # Snapshot the event log and the current learnings together under the store lock, so a
    # concurrent capture can't land between the two reads (its markdown present but its event not
    # yet logged) and produce transient, mismatched KPIs.
    with store_write_lock(loc):
        events = read_events(loc)
        present_ids = {entry.id for entry in load_learnings(loc)}
    recalls = [e for e in events if e.get("type") == "recall"]
    captures = [e for e in events if e.get("type") == "capture"]
    revises = [e for e in events if e.get("type") == "revise"]

    learnings_per_run = [int(e.get("counts", {}).get("learnings", 0)) for e in recalls]

    by_status = {"committed": 0, "reinforced": 0, "noop": 0}
    for e in captures:
        status = e.get("status")
        if status in by_status:
            by_status[status] += 1

    # Repeat-correction proxy (§11): among learning-directed corrections, how often a preference was
    # *reinforced* (already known) rather than newly *committed*. A rising rate = re-corrections
    # increasingly land on existing learnings, i.e. recurrence growth rather than new entries.
    # Reinforcements now arrive via BOTH capture-dedup (`reinforced`) and `revise(action=reinforce)`
    # — the latter is the primary path once `recall` surfaces the id — so both are counted.
    learning_committed = sum(
        1 for e in captures if e.get("status") == "committed" and e.get("polarity") == "learning"
    )
    revise_reinforcements = sum(1 for e in revises if e.get("action") == "reinforce")
    reinforcements = by_status["reinforced"] + revise_reinforcements
    reinforce_denom = learning_committed + reinforcements
    reinforcement_rate = (
        round(reinforcements / reinforce_denom, 4) if reinforce_denom else None
    )

    # % survived: of the learnings telemetry recorded creating, how many are still present.
    # Compared by ID, not count: a count-only check is fooled by mixed stores (e.g. create L1/L2,
    # remove them, import L99 -> present=1 <= committed=2 but L99 was never telemetry-created). We
    # only report a number when every currently-present learning is one telemetry recorded creating;
    # otherwise coverage is incomplete (pre-telemetry / imported markdown) and we return unknown
    # rather than a misleading figure. (Removals land in M2b; the KPI goes live once they exist.)
    # A learning is "created" either by a committed learning capture OR by a `revise` demote (which
    # mints a new learning from an issue). Both must be counted, else a demoted learning present in
    # the store looks like uncovered/imported markdown and suppresses the KPI.
    created_events = [
        e.get("entry_id")
        for e in captures
        if e.get("status") == "committed" and e.get("polarity") == "learning"
    ]
    created_events += [e.get("entry_id") for e in revises if e.get("action") == "demote"]
    created_events = [x for x in created_events if x is not None]
    committed_learning_ids = set(created_events)
    id_reused = len(created_events) != len(committed_learning_ids)
    if id_reused:
        # A learning id appears in multiple creation events → it was removed and a later capture
        # reused the id (next_id = max+1). The set then collapses two distinct ever-created
        # learnings into one, so still-present-vs-ever-created can't be computed honestly.
        survived_pct = {
            "value": None,
            "note": (
                "A learning id was reused across creation events (an entry was removed and its id "
                "later reassigned), so % survived cannot be computed honestly from the event log."
            ),
        }
    elif committed_learning_ids and present_ids <= committed_learning_ids:
        survived_pct = {
            "value": round(len(present_ids) / len(committed_learning_ids), 4),
            "note": None,
        }
    elif not present_ids and not committed_learning_ids:
        survived_pct = {"value": None, "note": "No learnings created yet."}
    else:
        survived_pct = {
            "value": None,
            "note": (
                "Incomplete telemetry coverage: the store has learnings not created via committed "
                "capture events (pre-telemetry or imported markdown), so % survived cannot be "
                "computed honestly from the event log."
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
