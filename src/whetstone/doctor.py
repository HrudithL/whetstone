"""``whetstone doctor <skill>`` — a read-only health check for a skill's learned loop (§M5d).

The real failure mode Whetstone can hit is a **silent no-op**: a store is attached but the host
never actually calls ``recall``/``capture``, so nothing is ever learned and nothing looks wrong.
``doctor`` diagnoses exactly that. It reports whether the store exists, whether recall/capture
events are landing (counts by type + the last event's timestamp), the embedding backend in use, and
the entry counts — and, when the loop looks dead (a store present but zero recalls), prints a
host-agnostic one-time "operating instructions" snippet to paste into the host.

It is a **diagnostic, never a mutator** — it never writes to the store and, in particular, never
edits a ``SKILL.md`` (the residue of the deliberately-declined ``wire`` tool: help the human wire
the loop, don't silently rewrite the shared skill doc).
"""

from __future__ import annotations

from collections import Counter

from .config import Config, load_config
from .store.access import load_issues, load_learnings
from .store.layout import is_store, read_registry, store_location
from .telemetry import read_events

_OPERATING_INSTRUCTIONS = (
    "This project uses Whetstone so skills learn from your feedback. Add these operating "
    "instructions to your host (system prompt / project rules / AGENTS.md):\n"
    "  • At the START of any task that uses an attached skill, call recall(skill, intent) with an "
    "elaborated intent (the styling dimensions, not the raw prompt).\n"
    "  • The MOMENT you act on feedback about that skill's output, call capture (for something "
    "new) or revise (for something recall already showed you), passing the recall run_id.\n"
    "  • Treat every returned issue as mandatory; apply learnings by their weight."
)


def doctor(skill: str, config: Config | None = None) -> dict:
    """Diagnose ``skill``'s learned loop; return a JSON-friendly report. Never mutates the store."""
    if config is None:
        config = load_config()
    loc = store_location(skill, config)
    exists = is_store(loc.path)
    attached = skill in read_registry(config)

    events = read_events(loc) if exists else []
    by_type = Counter(e.get("type") for e in events)
    recalls = by_type.get("recall", 0)
    last_event_ts = events[-1].get("ts") if events else None

    learnings = len(load_learnings(loc)) if exists else 0
    issues = len(load_issues(loc)) if exists else 0
    loop_healthy = exists and recalls > 0

    if not exists:
        diagnosis = (
            f"No store for {skill!r} yet. Call attach (or just recall) to create it, then wire the "
            "loop with the operating instructions below."
        )
    elif not loop_healthy:
        diagnosis = (
            f"Store exists but recall has NEVER run for {skill!r} — the learned loop looks "
            "unwired, so nothing is being recalled or captured. Add the operating instructions "
            "below to your host."
        )
    else:
        diagnosis = (
            f"Loop healthy: {recalls} recall(s), "
            f"{by_type.get('capture', 0)} capture(s), {by_type.get('revise', 0)} revise(s); "
            f"last event {last_event_ts}."
        )

    report = {
        "skill": skill,
        "slug": loc.slug,
        "path": str(loc.path),
        "exists": exists,
        "attached": attached,
        "backend": config.embedding_backend,
        "learnings": learnings,
        "issues": issues,
        "events": {"total": len(events), "by_type": dict(by_type), "last_event_ts": last_event_ts},
        "loop_healthy": loop_healthy,
        "diagnosis": diagnosis,
    }
    if not loop_healthy:
        report["operating_instructions"] = _OPERATING_INSTRUCTIONS
    return report
