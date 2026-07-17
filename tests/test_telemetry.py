"""Tests for the append-only ``events.jsonl`` log: shape, git-ignoring, and concurrent appends."""

from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

from whetstone.server import capture, recall
from whetstone.store.layout import store_location
from whetstone.telemetry import (
    append_event,
    emit_capture,
    emit_recall,
    events_path,
    read_events,
)


def _git_status(store_dir) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(store_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_append_and_read_roundtrip_stamps_ts(store):
    append_event(store, {"type": "recall", "run_id": "r-1"})
    events = read_events(store)
    assert len(events) == 1
    assert events[0]["type"] == "recall"
    assert events[0]["run_id"] == "r-1"
    assert "ts" in events[0]  # stamped automatically


def test_read_events_missing_log_is_empty(store):
    assert not events_path(store).exists()
    assert read_events(store) == []


def test_emit_recall_shape(store):
    emit_recall(store, "r-abc", "styling a table", ["L1", "L2"], ["I3"])
    (event,) = read_events(store)
    assert event["type"] == "recall"
    assert event["run_id"] == "r-abc"
    assert event["intent"] == "styling a table"
    assert event["returned"] == {"learnings": ["L1", "L2"], "issues": ["I3"]}
    assert event["counts"] == {"learnings": 2, "issues": 1}


def test_emit_capture_shape(store):
    emit_capture(store, "r-abc", "L7", "learning", "committed")
    (event,) = read_events(store)
    assert event["type"] == "capture"
    assert event["run_id"] == "r-abc"
    assert event["entry_id"] == "L7"
    assert event["polarity"] == "learning"
    assert event["status"] == "committed"


def test_lines_are_compact_single_line_json(store):
    emit_recall(store, "r-1", "intent one", ["L1"], [])
    emit_capture(store, "r-1", "L1", "learning", "committed")
    lines = events_path(store).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # exactly one line per event
    for line in lines:
        assert line == line.strip()  # no leading/trailing whitespace
        json.loads(line)  # each line parses on its own


def test_tools_emit_events_and_do_not_dirty_git(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")

    recall("gt", "right-align currency columns")
    result = capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    run_id = recall("gt", "currency alignment")["run_id"]
    capture(
        "gt",
        "learning",
        "Please right-align the currency columns for a clean look.",
        "currency",
        "prov",
        run_id=run_id,
    )

    loc = store_location("gt")
    events = read_events(loc)
    types = [e["type"] for e in events]
    assert types.count("recall") == 2
    assert types.count("capture") == 2
    capture_events = [e for e in events if e["type"] == "capture"]
    # First capture committed a new learning; both events reference the same entry id.
    assert capture_events[0]["status"] == "committed"
    assert capture_events[0]["entry_id"] == result["entry_id"]
    # The second capture reinforced that learning and carried the run_id from its recall.
    assert capture_events[1]["status"] == "reinforced"
    assert capture_events[1]["entry_id"] == result["entry_id"]
    assert capture_events[1]["run_id"] == run_id

    # events.jsonl exists but is git-ignored: it is not tracked and never dirties the working tree.
    store_dir = tmp_path / loc.slug
    assert (store_dir / "events.jsonl").exists()
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=str(store_dir), check=True, capture_output=True, text=True
    ).stdout
    assert "events.jsonl" not in tracked
    assert _git_status(store_dir) == ""  # clean working tree despite the append-only log


def test_concurrent_appends_do_not_corrupt_lines(store):
    n = 200

    def do(i: int):
        append_event(store, {"type": "capture", "run_id": f"r-{i}", "entry_id": f"L{i}"})

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(do, range(n)))

    lines = events_path(store).read_text(encoding="utf-8").splitlines()
    assert len(lines) == n  # every append landed on its own line, none lost or merged
    parsed = [json.loads(line) for line in lines]  # every line is intact JSON
    assert {e["run_id"] for e in parsed} == {f"r-{i}" for i in range(n)}


def test_append_event_is_best_effort_on_write_failure(tmp_path, monkeypatch):
    # A telemetry write failure (read-only events.jsonl, full disk, ...) must be swallowed, never
    # raised — otherwise it would turn an already-committed capture into an apparent failure the
    # caller retries, double-reinforcing the just-created learning.
    from whetstone import telemetry
    from whetstone.store.layout import ensure_store, store_location

    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    ensure_store("gt")
    loc = store_location("gt")

    def boom(*a, **k):
        raise OSError("read-only events.jsonl")

    monkeypatch.setattr(telemetry.os, "open", boom)
    telemetry.append_event(loc, {"type": "capture", "entry_id": "L1"})  # must not raise
    # And nothing was written, since the open failed.
    assert telemetry.read_events(loc) == []


def test_append_event_completes_line_on_partial_writes(tmp_path, monkeypatch):
    # os.write may accept only part of the buffer; append_event must loop so the whole line lands
    # (an unterminated fragment would concatenate with and corrupt the next event).
    import os

    from whetstone import telemetry
    from whetstone.store.layout import ensure_store, store_location

    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    ensure_store("gt")
    loc = store_location("gt")

    real_write = os.write

    def one_byte_at_a_time(fd, data):
        return real_write(fd, bytes(data[:1]))  # accept a single byte per call

    monkeypatch.setattr(telemetry.os, "write", one_byte_at_a_time)
    telemetry.append_event(loc, {"type": "capture", "entry_id": "L7", "status": "committed"})
    monkeypatch.undo()

    events = telemetry.read_events(loc)
    assert len(events) == 1
    assert events[0]["entry_id"] == "L7"


def test_read_events_tolerates_a_torn_non_ascii_tail(store):
    # An append interrupted mid-record (events use ensure_ascii=False) can leave a truncated UTF-8
    # sequence at EOF; read_events must skip it, not raise UnicodeDecodeError.
    append_event(store, {"type": "capture", "entry_id": "L1", "note": "café"})
    with open(events_path(store), "ab") as fh:
        fh.write('{"type":"capture","note":"café'.encode()[:-1])  # torn mid-"é", no newline
    events = read_events(store)
    assert len(events) == 1  # the intact first line survives; the torn tail is dropped
    assert events[0]["entry_id"] == "L1"
