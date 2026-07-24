"""Append-only per-store event log — ``events.jsonl`` (§5.1, §11).

Every ``recall`` and ``capture`` appends one compact JSON object per line to ``events.jsonl`` in the
store directory. This log is the runtime-agnostic substrate the statistics (§11) are computed from —
notably it is the *only* per-run denominator for application-rate metrics, since a run the user
simply accepts produces no follow-up ``capture``.

``events.jsonl`` is derived/local telemetry, not source of truth: the per-store ``.gitignore``
(see :mod:`whetstone.store.layout`) keeps it out of git history entirely.

Appends are made with an ``O_APPEND`` write of one newline-terminated line, looping until every
byte is written (``os.write`` may accept only part of the buffer on interruption or a space-limited
filesystem, and ignoring that would leave an unterminated fragment that concatenates with the next
append). On POSIX each ``O_APPEND`` write is positioned atomically, so concurrent appends from
multiple processes interleave whole writes rather than corrupting each other — no lock is required.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .store.layout import StoreLocation, store_events_lock

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
    # Telemetry is non-critical and always downstream of the real work (the markdown is already
    # written/committed by the time we log). A write failure — a read-only events.jsonl, a full
    # disk — must NEVER turn a successful recall/capture into a failure the caller would retry
    # (a retried capture would double-reinforce). So the append is best-effort.
    try:
        loc.path.mkdir(parents=True, exist_ok=True)
        # Serialize the whole-line append: a partial write completes over several os.write calls,
        # and the lock keeps the fragments contiguous so a concurrent writer can't interleave a
        # record between them. Separate from the store write lock, so a capture emitting while
        # holding that lock does not self-deadlock.
        with store_events_lock(loc):
            path = events_path(loc)
            data = line.encode("utf-8")
            # If a prior process died mid-append and left no trailing newline, begin a new line
            # first so this event isn't concatenated onto — and dropped together with — that torn
            # fragment; only the fragment is lost, not the first good event after a crash.
            if path.exists() and path.stat().st_size > 0:
                with open(path, "rb") as tail:
                    tail.seek(-1, os.SEEK_END)
                    if tail.read(1) != b"\n":
                        data = b"\n" + data
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                view = memoryview(data)
                while view:  # os.write may accept only part of the buffer; write the rest.
                    view = view[os.write(fd, view) :]
            finally:
                os.close(fd)
    except OSError:
        return


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
    scope: str | None = None,
) -> None:
    """Record a ``capture``: the entry it touched, its polarity, and the outcome ``status``
    (``committed`` | ``reinforced`` | ``noop`` | ``conflict``).

    ``scope`` is recorded so the M5a behavioral miner can attribute capture churn to a scope without
    reconstructing it from markdown (removed entries leave no markdown). Optional for back-compat:
    events written before M5a simply lack the key and the miner treats their scope as unknown.
    """
    append_event(
        loc,
        {
            "type": "capture",
            "run_id": run_id,
            "entry_id": entry_id,
            "polarity": polarity,
            "status": status,
            "scope": scope,
        },
    )


def emit_revise(
    loc: StoreLocation,
    run_id: str | None,
    entry_id: str,
    action: str,
    status: str,
    scope: str | None = None,
) -> None:
    """Record a ``revise``: the entry it touched, the ``action`` applied, and the outcome ``status``
    (``revised`` | ``removed`` | ``promoted`` | ``demoted`` | ``reinforced``). Only emitted when a
    mutation actually commits — a bare ``needs_confirmation`` prompt changes nothing and logs
    nothing. ``scope`` is recorded for the M5a miner (see :func:`emit_capture`)."""
    append_event(
        loc,
        {
            "type": "revise",
            "run_id": run_id,
            "entry_id": entry_id,
            "action": action,
            "status": status,
            "scope": scope,
        },
    )


def emit_compaction(
    loc: StoreLocation,
    *,
    retired: int,
    merged_scopes: int,
    deduped: int,
) -> None:
    """Record a ``compact`` maintenance pass (§7): how many learnings were retired, how many scopes
    folded into another (anti-fragmentation), and how many near-duplicate entries collapsed. Emitted
    only when the pass actually changed the store (a no-op compaction logs nothing), so metrics can
    see the maintenance that mattered."""
    append_event(
        loc,
        {
            "type": "compaction",
            "retired": retired,
            "merged_scopes": merged_scopes,
            "deduped": deduped,
        },
    )


def emit_promote(
    loc: StoreLocation,
    *,
    source_skill: str,
    source_id: str,
    global_id: str,
    polarity: str,
) -> None:
    """Record a promotion into the learned global layer (§M5e): the source skill + entry it came
    from and the new ``__global__`` id it now lives under. Emitted to the global store's log."""
    append_event(
        loc,
        {
            "type": "promote",
            "source_skill": source_skill,
            "source_id": source_id,
            "global_id": global_id,
            "polarity": polarity,
        },
    )


def emit_import(
    loc: StoreLocation,
    *,
    pack: str,
    mode: str,
    committed: int,
    merged: int,
    conflicts: int,
) -> None:
    """Record a preference-pack import (§M5c): the pack name, the mode (``merge``/``replace``), and
    how many incoming entries were newly committed, folded into an existing entry, or surfaced as an
    unresolved conflict (merge only). Emitted once per import that changed the store."""
    append_event(
        loc,
        {
            "type": "import",
            "pack": pack,
            "mode": mode,
            "committed": committed,
            "merged": merged,
            "conflicts": conflicts,
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
    # Decode leniently: an append interrupted mid-record (events use ensure_ascii=False) can leave a
    # truncated UTF-8 sequence at EOF; decoding bytes with errors="ignore" drops that torn tail
    # instead of raising, so a partial final line never fails the whole read (§ best-effort).
    events: list[dict] = []
    for line in path.read_bytes().decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
