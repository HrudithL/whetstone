"""Whole-store reads and writes over the per-scope markdown files.

The markdown layer (:mod:`whetstone.store.markdown`) parses/serializes a single scope file. This
module works across *all* scope files in a store: loading every entry, allocating the next
monotonic id, and adding/updating a single entry in its scope file. Each scope maps 1:1 to a file
via :func:`whetstone.store.slug.scope_filename` (the hash suffix guarantees no two scopes share a
file), so a file only ever holds entries of one scope.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from .entries import IssueEntry, LearningEntry
from .layout import StoreLocation
from .markdown import (
    parse_issues,
    parse_learnings,
    write_issues,
    write_learnings,
)
from .slug import scope_filename


def load_learnings(loc: StoreLocation) -> list[LearningEntry]:
    """Every learning across all scope files, in filename order."""
    entries: list[LearningEntry] = []
    for path in sorted(loc.learnings_dir.glob("*.md")):
        entries.extend(parse_learnings(path.read_text(encoding="utf-8")))
    return entries


def load_issues(loc: StoreLocation) -> list[IssueEntry]:
    """Every issue across all scope files, in filename order."""
    entries: list[IssueEntry] = []
    for path in sorted(loc.issues_dir.glob("*.md")):
        entries.extend(parse_issues(path.read_text(encoding="utf-8")))
    return entries


def _max_id_number(ids: list[str]) -> int:
    highest = 0
    for entry_id in ids:
        try:
            highest = max(highest, int(entry_id[1:]))
        except ValueError:  # pragma: no cover - defensive; parser enforces the id shape
            continue
    return highest


def next_id(loc: StoreLocation, polarity: str) -> str:
    """The next monotonic id for ``polarity`` — ``L``/``I`` + (max existing number + 1)."""
    if polarity == "learning":
        return f"L{_max_id_number([e.id for e in load_learnings(loc)]) + 1}"
    if polarity == "issue":
        return f"I{_max_id_number([e.id for e in load_issues(loc)]) + 1}"
    raise ValueError(f"polarity must be 'learning' or 'issue', got {polarity!r}")


def save_learning(loc: StoreLocation, entry: LearningEntry) -> None:
    """Insert or replace ``entry`` in its scope file (matched by id), leaving siblings intact."""
    path = loc.learnings_dir / scope_filename(entry.scope)
    existing = parse_learnings(path.read_text(encoding="utf-8")) if path.exists() else []
    existing = [e for e in existing if e.id != entry.id]
    existing.append(entry)
    write_learnings(path, existing)


def save_issue(loc: StoreLocation, entry: IssueEntry) -> None:
    """Insert or replace ``entry`` in its scope file (matched by id), leaving siblings intact."""
    path = loc.issues_dir / scope_filename(entry.scope)
    existing = parse_issues(path.read_text(encoding="utf-8")) if path.exists() else []
    existing = [e for e in existing if e.id != entry.id]
    existing.append(entry)
    write_issues(path, existing)


def reinforce_learning(
    loc: StoreLocation, entry_id: str, when: date | None = None
) -> LearningEntry:
    """Bump ``entry_id``'s recurrence by 1 and refresh ``last_seen`` in place; return the result."""
    stamp = when or date.today()
    for path in sorted(loc.learnings_dir.glob("*.md")):
        entries = parse_learnings(path.read_text(encoding="utf-8"))
        for i, e in enumerate(entries):
            if e.id == entry_id:
                entries[i] = replace(e, recurrence=e.recurrence + 1, last_seen=stamp)
                write_learnings(path, entries)
                return entries[i]
    raise KeyError(f"no learning with id {entry_id!r}")
