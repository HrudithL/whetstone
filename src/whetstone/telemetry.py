"""Append-only per-store event log — ``events.jsonl`` (§5.1, §11).

Every ``recall`` and ``capture`` appends one compact JSON object per line to ``events.jsonl`` in the
store directory. This log is the runtime-agnostic substrate the statistics (§11) are computed from —
notably it is the *only* per-run denominator for application-rate metrics, since a run the user
simply accepts produces no follow-up ``capture``.

``events.jsonl`` is derived/local telemetry, not source of truth: the per-store ``.gitignore``
(see :mod:`whetstone.store.layout`) keeps it out of git history entirely.

Appends are made with a single ``O_APPEND`` write of one newline-terminated line. On POSIX an
``O_APPEND`` write is positioned atomically, and a write this small is delivered in one piece, so
concurrent appends from multiple processes interleave whole lines rather than corrupting each other
— no lock is required on the write path.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .store.layout import StoreLocation

EVENTS_NAME = "events.jsonl"


def events_path(loc: StoreLocation) -> Path:
    return loc.path / EVENTS_NAME


def append_event(loc: StoreLocation, event: dict) -> None:
    """Append one event as a compact JSON line, stamping ``ts`` (UTC ISO-8601) if absent.

    The whole line is written in a single ``O_APPEND`` ``os.write`` so concurrent writers never
    interleave partial lines (see module docstring).
    """
    record = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), **event}
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
    loc.path.mkdir(parents=True, exist_ok=True)
    fd = os.open(events_path(loc), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def emit_recall(
    loc: StoreLocation,
    run_id: str,
    intent: str,
    learning_ids: list[str],
    issue_ids: list[str],
) -> None:
    """Record a ``recall`` run: the intent and the learning/issue ids it returned (§5.2, §11)."""
    append_event(
        loc,
        {
            "type": "recall",
            "run_id": run_id,
            "intent": intent,
            "returned": {"learnings": learning_ids, "issues": issue_ids},
            "counts": {"learnings": len(learning_ids), "issues": len(issue_ids)},
        },
    )


def emit_capture(
    loc: StoreLocation,
    run_id: str | None,
    entry_id: str,
    polarity: str,
    status: str,
) -> None:
    """Record a ``capture``: the entry it touched, its polarity, and the outcome ``status``
    (``committed`` | ``reinforced`` | ``noop``)."""
    append_event(
        loc,
        {
            "type": "capture",
            "run_id": run_id,
            "entry_id": entry_id,
            "polarity": polarity,
            "status": status,
        },
    )


def read_events(loc: StoreLocation) -> list[dict]:
    """Read every event line, skipping blank lines. Missing log -> empty list.

    A trailing/torn final line (a write that never completed) is tolerated: only a line that fails
    to parse as JSON is skipped, so a partial tail never fails the whole read.
    """
    path = events_path(loc)
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
