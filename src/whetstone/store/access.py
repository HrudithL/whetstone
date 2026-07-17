"""Whole-store reads and writes over the per-scope markdown files.

The markdown layer (:mod:`whetstone.store.markdown`) parses/serializes a single scope file. This
module works across *all* scope files in a store: loading every entry, allocating the next
monotonic id, and adding/updating a single entry in its scope file. Each scope maps 1:1 to a file
via :func:`whetstone.store.slug.scope_filename` (the hash suffix guarantees no two scopes share a
file), so a file only ever holds entries of one scope.
"""

from __future__ import annotations

import re
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

_MAX_TITLE = 60


def _title_from_body(body: str, fallback: str) -> str:
    """A short single-line heading for a moved entry, distilled from ``body``'s first sentence.

    Mirrors the derivation ``capture`` uses; ``fallback`` (the source entry's title) is kept when
    the body is unchanged/empty so a plain move never loses the heading.
    """
    collapsed = " ".join(body.split())
    if not collapsed:
        return fallback
    first_sentence = re.split(r"(?<=[.!?])\s", collapsed, maxsplit=1)[0]
    return first_sentence[:_MAX_TITLE].strip() or collapsed[:_MAX_TITLE].strip()


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


def find_learning(loc: StoreLocation, entry_id: str) -> LearningEntry | None:
    """The learning with ``entry_id``, or None."""
    for e in load_learnings(loc):
        if e.id == entry_id:
            return e
    return None


def find_issue(loc: StoreLocation, entry_id: str) -> IssueEntry | None:
    """The issue with ``entry_id``, or None."""
    for e in load_issues(loc):
        if e.id == entry_id:
            return e
    return None


def set_learning_recurrence(
    loc: StoreLocation, entry_id: str, recurrence: int
) -> LearningEntry:
    """Set ``entry_id``'s recurrence to an explicit value in place; return the result.

    Unlike :func:`reinforce_learning` this does NOT touch ``last_seen`` — weakening a preference
    (the user going against it) must not also refresh its recency, which would perversely raise its
    weight.
    """
    for path in sorted(loc.learnings_dir.glob("*.md")):
        entries = parse_learnings(path.read_text(encoding="utf-8"))
        for i, e in enumerate(entries):
            if e.id == entry_id:
                entries[i] = replace(e, recurrence=recurrence)
                write_learnings(path, entries)
                return entries[i]
    raise KeyError(f"no learning with id {entry_id!r}")


def remove_entry(loc: StoreLocation, entry_id: str) -> bool:
    """Delete a learning or issue (by id prefix) from its scope file; True iff it existed."""
    if entry_id.startswith("L"):
        directory, parse, write = loc.learnings_dir, parse_learnings, write_learnings
    elif entry_id.startswith("I"):
        directory, parse, write = loc.issues_dir, parse_issues, write_issues
    else:
        raise ValueError(f"entry id must start with 'L' or 'I', got {entry_id!r}")
    for path in sorted(directory.glob("*.md")):
        entries = parse(path.read_text(encoding="utf-8"))
        kept = [e for e in entries if e.id != entry_id]
        if len(kept) != len(entries):
            write(path, kept)
            return True
    return False


def promote_learning_to_issue(
    loc: StoreLocation,
    entry_id: str,
    new_id: str,
    *,
    body: str | None = None,
    scope: str | None = None,
) -> IssueEntry:
    """Move learning ``entry_id`` to ``issues/`` under ``new_id``, dropping its scoring fields (§6).

    ``body``/``scope`` supply the objective rewording promotion requires; when omitted the source
    prose/scope carries over. The heading is re-derived from the (possibly reworded) body.
    """
    learning = find_learning(loc, entry_id)
    if learning is None:
        raise KeyError(f"no learning with id {entry_id!r}")
    new_body = body.strip() if body else learning.body
    issue = IssueEntry(
        id=new_id,
        title=_title_from_body(new_body, learning.title),
        body=new_body,
        scope=scope or learning.scope,
        provenance=learning.provenance,
    )
    save_issue(loc, issue)
    remove_entry(loc, entry_id)
    return issue


def demote_issue_to_learning(
    loc: StoreLocation,
    entry_id: str,
    new_id: str,
    *,
    seed_recurrence: int,
    when: date,
    body: str | None = None,
    scope: str | None = None,
) -> LearningEntry:
    """Move issue ``entry_id`` to ``learnings/`` under ``new_id``, seeding scoring fields (§5.2).

    Recurrence is seeded to ``seed_recurrence`` and ``first_seen``/``last_seen`` to ``when``.
    Optional ``body``/``scope`` supply reworded prose (used when softening a rule in conflict
    resolution).
    """
    issue = find_issue(loc, entry_id)
    if issue is None:
        raise KeyError(f"no issue with id {entry_id!r}")
    new_body = body.strip() if body else issue.body
    learning = LearningEntry(
        id=new_id,
        title=_title_from_body(new_body, issue.title),
        body=new_body,
        scope=scope or issue.scope,
        provenance=issue.provenance,
        recurrence=seed_recurrence,
        first_seen=when,
        last_seen=when,
    )
    save_learning(loc, learning)
    remove_entry(loc, entry_id)
    return learning
