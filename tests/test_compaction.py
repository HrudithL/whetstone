"""End-to-end tests for the out-of-band `compact` maintenance pass (§7, §5.4, §15).

Entries are seeded straight to markdown (the source of truth); `today` is injected so the recency
decay that drives retirement is deterministic (matches M2a/M2b). Uses the dependency-free
HashingBackend via the shared fixtures (no torch/network).
"""

from __future__ import annotations

import subprocess
from datetime import date

from conftest import make_issue, make_learning, seed
from whetstone.compaction import compact
from whetstone.server import main
from whetstone.store.access import load_issues, load_learnings, next_id
from whetstone.store.layout import commit_store
from whetstone.telemetry import read_events


def _commit_count(loc) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(loc.path),
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


def _clean_seed(loc, learnings=(), issues=()) -> None:
    """Seed entries and commit, so a following compact adds exactly one commit off a clean tree."""
    seed(loc, learnings=learnings, issues=issues)
    commit_store(loc, "seed")


def _md_files(directory) -> list[str]:
    return sorted(p.name for p in directory.glob("*.md"))


def _fresh(entry_id, body, scope, recurrence=5):
    """A high-weight learning that retirement keeps (recent last_seen, healthy recurrence)."""
    e = make_learning(entry_id, body, scope, recurrence=recurrence)
    e.first_seen = date(2026, 2, 1)
    e.last_seen = date(2026, 2, 1)
    return e


TODAY = date(2026, 3, 1)


# --------------------------------------------------------------------------- retire (step 3)


def test_retire_drops_stale_keeps_fresh(store, config):
    stale = make_learning("L1", "Prefer teal accents.", "color", recurrence=1)
    stale.last_seen = date(2024, 1, 1)  # ~2.4y old -> weight well below threshold
    fresh = _fresh("L2", "Right-align currency columns.", "currency")
    _clean_seed(store, learnings=[stale, fresh])

    result = compact("gt", today=TODAY, config=config)

    ids = {e.id for e in load_learnings(store)}
    assert ids == {"L2"}  # stale retired, fresh kept
    assert result["retired"] == 1


def test_issues_are_never_retired(store, config):
    # An issue has no scoring fields and is never scored; even seeded "long ago" it must survive.
    _clean_seed(store, issues=[make_issue("I1", "Never ship secrets in logs.", "logging")])

    compact("gt", today=date(2030, 1, 1), config=config)

    assert [e.id for e in load_issues(store)] == ["I1"]


def test_retired_ids_are_not_reused(store, config):
    stale = make_learning("L1", "Prefer teal accents.", "color", recurrence=1)
    stale.last_seen = date(2024, 1, 1)
    _clean_seed(store, learnings=[stale])

    compact("gt", today=TODAY, config=config)

    assert load_learnings(store) == []
    assert next_id(store, "learning") == "L2"  # L1 retired but its number is never minted again


# --------------------------------------------------------------------------- dedupe (step 1)


def test_dedupe_collapses_and_combines_recurrence(store, config):
    body = "Right-align currency columns in financial tables."
    a = _fresh("L1", body, "currency", recurrence=2)
    b = _fresh("L2", body, "currency", recurrence=3)  # identical body, same scope -> duplicate
    _clean_seed(store, learnings=[a, b])

    result = compact("gt", today=TODAY, config=config)

    (survivor,) = load_learnings(store)
    assert survivor.id == "L1"  # first representative kept
    assert survivor.recurrence == 5  # 2 + 3 combined
    assert result["deduped"] == 1


# --------------------------------------------------------------------------- merge scopes (step 2)


def test_overlapping_scopes_merge_unrelated_stay(store, config):
    body = "Right-align currency columns in financial tables."
    a = _fresh("L1", body, "currency columns")
    b = _fresh("L2", body, "currency cols")  # identical entry -> identical centroid -> merges
    other = _fresh("L3", "Use a large serif heading font for section titles.", "typography")
    _clean_seed(store, learnings=[a, b])
    _clean_seed(store, learnings=[other])

    result = compact("gt", today=TODAY, config=config)

    entries = {e.id: e for e in load_learnings(store)}
    assert set(entries) == {"L1", "L2", "L3"}  # nothing retired, nothing deduped
    assert entries["L1"].scope == entries["L2"].scope  # folded into a single canonical scope
    assert entries["L3"].scope == "typography"  # unrelated scope untouched
    # Two currency scope files collapsed to one; typography's file remains -> 2 files total.
    assert len(_md_files(store.learnings_dir)) == 2
    assert result["merged_scopes"] == 1


# --------------------------------------------------------------------------- commit / telemetry


def test_compaction_commits_once_and_emits_event(store, config):
    body = "Right-align currency columns in financial tables."
    dupes = [_fresh("L1", body, "currency", 2), _fresh("L2", body, "currency", 3)]
    _clean_seed(store, learnings=dupes)
    before = _commit_count(store)

    compact("gt", today=TODAY, config=config)

    assert _commit_count(store) == before + 1  # exactly one compact commit
    events = [e for e in read_events(store) if e["type"] == "compaction"]
    assert len(events) == 1
    assert events[0] == {**events[0], "deduped": 1, "merged_scopes": 0, "retired": 0}


def test_noop_compaction_makes_no_commit(store, config):
    _clean_seed(store, learnings=[_fresh("L1", "Right-align currency columns.", "currency")])
    before = _commit_count(store)

    result = compact("gt", today=TODAY, config=config)

    assert result == {
        "skill": "gt",
        "deduped": 0,
        "merged_scopes": 0,
        "retired": 0,
        "committed": False,
        "findings": [],
        "report_path": None,
    }
    assert _commit_count(store) == before  # nothing changed -> no commit
    assert [e for e in read_events(store) if e["type"] == "compaction"] == []


# --------------------------------------------------------------------------- CLI


def test_cli_compact_runs_and_prints_summary(store, config, capsys):
    import json

    stale = make_learning("L1", "Prefer teal accents.", "color", recurrence=1)
    stale.last_seen = date(2024, 1, 1)
    _clean_seed(store, learnings=[stale])

    main(["compact", "gt"])

    summary = json.loads(capsys.readouterr().out)
    assert summary["skill"] == "gt"
    assert summary["retired"] == 1
    assert summary["committed"] is True
    assert load_learnings(store) == []
