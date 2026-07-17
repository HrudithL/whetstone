"""Markdown reader/writer implementing the §5.1 block contract.

Block contract (LEARNING_SKILLS_DESIGN.md §5.1):

    ## L12 · Right-align currency columns
    - recurrence: 4
    - first_seen: 2026-05-01
    - last_seen: 2026-07-10
    - scope: currency columns
    - provenance: "2026-07-10 — 'make the revenue column right-aligned'"

    Right-align currency columns and drop vertical gridlines. The user consistently
    prefers a clean, numeric-first look for financial tables.

Split on ``## ``; the heading is ``<id> · <title>``; a bullet list carries the metadata; a blank
line separates it from the prose body. Issue blocks are identical minus the
``recurrence``/``first_seen``/``last_seen`` fields. ``weight`` is derived and NEVER written.

Writes are atomic (temp file + rename), and parse -> serialize -> parse is stable.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

from .entries import IssueEntry, LearningEntry

_HEADING_SEP = " · "
_LEARNING_KEYS = ("recurrence", "first_seen", "last_seen", "scope", "provenance")
_ISSUE_KEYS = ("scope", "provenance")


class MarkdownParseError(ValueError):
    """Raised when a store markdown file does not satisfy the block contract."""


# --------------------------------------------------------------------------- parsing


def _split_blocks(text: str) -> list[list[str]]:
    """Split file text into blocks, each a list of lines starting at a ``## `` heading."""
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = [line]
            blocks.append(current)
        elif current is not None:
            current.append(line)
        elif line.strip():
            raise MarkdownParseError(
                f"content before first '## ' heading: {line!r}"
            )
    return blocks


def _parse_block(lines: list[str]) -> tuple[str, str, dict[str, str], str]:
    """Parse one block into (id, title, metadata, body)."""
    heading = lines[0][len("## ") :].strip()
    if _HEADING_SEP not in heading:
        raise MarkdownParseError(
            f"heading must be '<id> · <title>', got {heading!r}"
        )
    entry_id, title = heading.split(_HEADING_SEP, 1)
    entry_id, title = entry_id.strip(), title.strip()
    if not entry_id or not title:
        raise MarkdownParseError(f"heading has an empty id or title: {heading!r}")

    metadata: dict[str, str] = {}
    i = 1
    while i < len(lines) and lines[i].startswith("- "):
        item = lines[i][len("- ") :]
        if ": " not in item:
            raise MarkdownParseError(f"metadata bullet must be '- key: value', got {lines[i]!r}")
        key, value = item.split(": ", 1)
        metadata[key.strip()] = value.strip()
        i += 1

    # Exactly one blank line separates metadata from the body; tolerate its absence at EOF.
    if i < len(lines) and lines[i].strip() == "":
        i += 1

    body = "\n".join(lines[i:]).strip()
    return entry_id, title, metadata, body


def _require(metadata: dict[str, str], keys: tuple[str, ...], entry_id: str) -> None:
    missing = [k for k in keys if k not in metadata]
    if missing:
        raise MarkdownParseError(f"entry {entry_id!r} is missing metadata: {', '.join(missing)}")


def parse_learnings(text: str) -> list[LearningEntry]:
    """Parse the text of a ``learnings/<scope>.md`` file into :class:`LearningEntry` objects."""
    entries: list[LearningEntry] = []
    for block in _split_blocks(text):
        entry_id, title, meta, body = _parse_block(block)
        _require(meta, _LEARNING_KEYS, entry_id)
        try:
            recurrence = int(meta["recurrence"])
        except ValueError as exc:
            raise MarkdownParseError(
                f"entry {entry_id!r} has a non-integer recurrence: {meta['recurrence']!r}"
            ) from exc
        entries.append(
            LearningEntry(
                id=entry_id,
                title=title,
                body=body,
                scope=meta["scope"],
                provenance=meta["provenance"],
                recurrence=recurrence,
                first_seen=_parse_date(meta["first_seen"], entry_id, "first_seen"),
                last_seen=_parse_date(meta["last_seen"], entry_id, "last_seen"),
            )
        )
    return entries


def parse_issues(text: str) -> list[IssueEntry]:
    """Parse the text of an ``issues/<scope>.md`` file into :class:`IssueEntry` objects."""
    entries: list[IssueEntry] = []
    for block in _split_blocks(text):
        entry_id, title, meta, body = _parse_block(block)
        _require(meta, _ISSUE_KEYS, entry_id)
        entries.append(
            IssueEntry(
                id=entry_id,
                title=title,
                body=body,
                scope=meta["scope"],
                provenance=meta["provenance"],
            )
        )
    return entries


def _parse_date(value: str, entry_id: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MarkdownParseError(
            f"entry {entry_id!r} has an invalid {field_name} date: {value!r}"
        ) from exc


# --------------------------------------------------------------------------- serializing


def _single_line(value: str) -> str:
    """Collapse newlines/CRs in a heading or metadata value to single spaces.

    Headings and metadata bullets are single-line by contract. Sanitizing on write stops a
    model-/user-supplied value containing a newline (or a ``## `` / ``- `` line) from forging extra
    metadata bullets or a bogus entry block when the file is read back.
    """
    return " ".join(str(value).splitlines()).strip()


def _serialize_block(entry_id: str, title: str, metadata: list[tuple[str, str]], body: str) -> str:
    lines = [f"## {entry_id}{_HEADING_SEP}{_single_line(title)}"]
    lines.extend(f"- {key}: {_single_line(value)}" for key, value in metadata)
    lines.append("")
    lines.append(body.strip())
    return "\n".join(lines)


def serialize_learnings(entries: list[LearningEntry]) -> str:
    """Serialize learnings to markdown. ``weight`` is derived and never written."""
    blocks = [
        _serialize_block(
            e.id,
            e.title,
            [
                ("recurrence", str(e.recurrence)),
                ("first_seen", e.first_seen.isoformat()),
                ("last_seen", e.last_seen.isoformat()),
                ("scope", e.scope),
                ("provenance", e.provenance),
            ],
            e.body,
        )
        for e in entries
    ]
    return "\n\n".join(blocks) + "\n" if blocks else ""


def serialize_issues(entries: list[IssueEntry]) -> str:
    """Serialize issues to markdown (no scoring fields)."""
    blocks = [
        _serialize_block(
            e.id,
            e.title,
            [
                ("scope", e.scope),
                ("provenance", e.provenance),
            ],
            e.body,
        )
        for e in entries
    ]
    return "\n\n".join(blocks) + "\n" if blocks else ""


# --------------------------------------------------------------------------- atomic writes


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def write_learnings(path: Path, entries: list[LearningEntry]) -> None:
    """Atomically write learnings to ``path``."""
    _atomic_write(path, serialize_learnings(entries))


def write_issues(path: Path, entries: list[IssueEntry]) -> None:
    """Atomically write issues to ``path``."""
    _atomic_write(path, serialize_issues(entries))
