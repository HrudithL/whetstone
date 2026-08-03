"""The derived, rebuildable ``index.sqlite`` (§5.1, §5.4).

The markdown is the source of truth; this sqlite file is a derived cache of embeddings that any call
can regenerate from the markdown. It holds, per store:

- **scopes** — for each ``(polarity, scope)``: the ``centroid`` (mean of the scope's entry vectors)
  and the ``phrase`` vector (the scope label embedded). Scope *matching* uses only these two (§5.4).
- **entries** — per entry: its vector (retained because the MMR diverse cap scores over per-entry
  similarity), plus the metadata retrieval surfaces (recurrence, dates, title, body, scope).
- **meta** — a fingerprint of the markdown + backend identity, so :func:`ensure_index` can tell
  whether the cache is stale and rebuild only when needed.

Vectors are stored as packed 32-bit floats (``array('f')``) — compact and dependency-free. Cosine
similarity is brute-force over these rows (§5.4: no ANN library at this scale).
"""

from __future__ import annotations

import hashlib
import sqlite3
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ..embeddings import EmbeddingBackend
from .entries import IssueEntry, LearningEntry
from .layout import StoreLocation, store_write_lock
from .markdown import parse_issues, parse_learnings

INDEX_NAME = "index.sqlite"
# Bumped whenever the derived-row shape changes (independent of the markdown/backend), so an index
# built by an older schema is treated as stale and rebuilt rather than read with a missing column.
# v2 added the per-entry ``last_seen`` column (the recency input, §4.4).
_SCHEMA_VERSION = 2
# How long a connection waits on SQLite's own lock (instead of failing immediately with "database
# is locked") when it genuinely contends with another connection's transaction — see
# :func:`rebuild_index`'s module-level rationale for why contention is expected to be brief.
BUSY_TIMEOUT_SECONDS = 5.0


@dataclass
class ScopeVectors:
    """A scope's two matching vectors (§5.4)."""

    scope: str
    centroid: list[float]
    phrase: list[float]


@dataclass
class IndexedEntry:
    """A single entry with its vector and the fields retrieval surfaces."""

    id: str
    polarity: str
    scope: str
    vector: list[float]
    recurrence: int | None
    title: str
    body: str
    # The recency input (§4.4), ISO date string. None for issues (they don't decay) and for a
    # learning with no recorded date (defensive — the parser always supplies one).
    last_seen: str | None


def index_path(loc: StoreLocation) -> Path:
    return loc.path / INDEX_NAME


def entry_text(title: str, body: str) -> str:
    """The text embedded to represent an entry (its content, not its scope label)."""
    return f"{title}\n{body}".strip()


# --------------------------------------------------------------------------- packing


def _pack(vec: list[float]) -> bytes:
    return array("f", vec).tobytes()


def _unpack(blob: bytes) -> list[float]:
    arr = array("f")
    arr.frombytes(blob)
    return arr.tolist()


# --------------------------------------------------------------------------- fingerprint


def _snapshot(directory: Path) -> list[tuple[str, bytes]]:
    """Read every ``*.md`` file's bytes once, in filename order: a point-in-time snapshot."""
    return [(p.name, p.read_bytes()) for p in sorted(directory.glob("*.md"))]


def _fingerprint_of(
    backend: EmbeddingBackend,
    learning_files: list[tuple[str, bytes]],
    issue_files: list[tuple[str, bytes]],
) -> str:
    """Hash the backend identity + the given file snapshot; changes iff the index would differ.

    ``model_id`` is included (not just class + dim) so switching to a different embedding model of
    the same dimensionality invalidates the index instead of silently reusing incompatible vectors.
    Taking the file bytes as an argument lets ``rebuild_index`` fingerprint the EXACT snapshot it
    built the rows from, so the stored fingerprint can't advertise fresh over stale vectors.
    """
    hasher = hashlib.sha1()
    hasher.update(f"v{_SCHEMA_VERSION}\0".encode())
    hasher.update(f"{type(backend).__name__}:{backend.model_id}:{backend.dim}\0".encode())
    for files in (learning_files, issue_files):
        for name, data in files:
            hasher.update(name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(data)
            hasher.update(b"\0")
    return hasher.hexdigest()


def _fingerprint(loc: StoreLocation, backend: EmbeddingBackend) -> str:
    """The current-on-disk fingerprint, used by the staleness check to compare against the stored
    one. A fresh read here is correct: it detects any change since the index was built."""
    return _fingerprint_of(backend, _snapshot(loc.learnings_dir), _snapshot(loc.issues_dir))


# --------------------------------------------------------------------------- build


def _centroid(vectors: list[list[float]], dim: int) -> list[float]:
    if not vectors:
        return [0.0] * dim
    total = [0.0] * dim
    for vec in vectors:
        for i, value in enumerate(vec):
            total[i] += value
    count = len(vectors)
    return [value / count for value in total]


def rebuild_index(loc: StoreLocation, backend: EmbeddingBackend) -> None:
    """Regenerate ``index.sqlite`` from the markdown store (fully idempotent).

    The parsed entries AND the stored fingerprint are both derived from a single file snapshot, so
    if the markdown is edited (outside Whetstone) mid-rebuild the published fingerprint can never
    advertise fresh over the stale vectors that were actually indexed.

    Rewrites the rows **in place**, inside one transaction, rather than building a separate temp
    file and ``os.replace``-ing it over the live one. The previous swap-based design relied on a
    POSIX-only guarantee — replacing a file while another process still has it open is fine on
    POSIX (the old inode lives on under that open handle) but raises ``PermissionError`` on
    Windows, which does not allow replacing a file that anything still has open. In-place
    DELETE+INSERT-then-commit gives the same "a reader never sees a partial rebuild" property
    through SQLite's own transaction isolation instead: a reader's transaction (see
    ``retrieve()``'s explicit ``BEGIN``) blocks this commit until it finishes, and any read that
    starts after this commits sees the new rows atomically — a guarantee that holds identically on
    every platform, since it never depends on OS-level file-replace semantics.
    """
    learning_files = _snapshot(loc.learnings_dir)
    issue_files = _snapshot(loc.issues_dir)
    learnings: list[LearningEntry] = [
        e for _, data in learning_files for e in parse_learnings(data.decode("utf-8"))
    ]
    issues: list[IssueEntry] = [
        e for _, data in issue_files for e in parse_issues(data.decode("utf-8"))
    ]
    fingerprint = _fingerprint_of(backend, learning_files, issue_files)

    learning_scopes = sorted({e.scope for e in learnings})
    issue_scopes = sorted({e.scope for e in issues})

    # One batched embed call: entry texts first, then scope-phrase texts.
    entry_texts = [entry_text(e.title, e.body) for e in learnings]
    entry_texts += [entry_text(e.title, e.body) for e in issues]
    phrase_texts = list(learning_scopes) + list(issue_scopes)
    all_vectors = backend.embed(entry_texts + phrase_texts) if (entry_texts + phrase_texts) else []

    n_learn = len(learnings)
    n_issue = len(issues)
    learn_vecs = all_vectors[:n_learn]
    issue_vecs = all_vectors[n_learn : n_learn + n_issue]
    phrase_vecs = all_vectors[n_learn + n_issue :]
    learn_phrase = dict(zip(learning_scopes, phrase_vecs[: len(learning_scopes)], strict=True))
    issue_phrase = dict(zip(issue_scopes, phrase_vecs[len(learning_scopes) :], strict=True))

    dim = backend.dim
    scope_rows: list[tuple[str, str, bytes, bytes]] = []
    entry_rows: list[tuple[str, str, str, bytes, int | None, str, str, str | None]] = []

    _collect(
        "learning", learnings, learn_vecs, learn_phrase, dim, scope_rows, entry_rows
    )
    _collect("issue", issues, issue_vecs, issue_phrase, dim, scope_rows, entry_rows)

    path = index_path(loc)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_SECONDS)
    try:
        _create_schema(conn)
        # Clear the previous rows before inserting the new ones, all inside one transaction — a
        # reader's own transaction (see retrieve()) blocks this commit until it finishes, so a
        # concurrent read is never exposed to the brief empty-then-repopulated window.
        conn.execute("DELETE FROM scopes")
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM meta")
        conn.executemany(
            "INSERT INTO scopes (polarity, scope, centroid, phrase) VALUES (?, ?, ?, ?)",
            scope_rows,
        )
        conn.executemany(
            "INSERT INTO entries "
            "(id, polarity, scope, vector, recurrence, title, body, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            entry_rows,
        )
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('fingerprint', ?)",
            (fingerprint,),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _collect(
    polarity: str,
    entries: list[LearningEntry] | list[IssueEntry],
    entry_vecs: list[list[float]],
    phrase_by_scope: dict[str, list[float]],
    dim: int,
    scope_rows: list[tuple[str, str, bytes, bytes]],
    entry_rows: list[tuple[str, str, str, bytes, int | None, str, str, str | None]],
) -> None:
    by_scope: dict[str, list[list[float]]] = {}
    # mypy infers `object` (not `LearningEntry | IssueEntry`) for a zip() over a `list[A] | list[B]`
    # first argument — a known overload-resolution gap, not a real typing ambiguity here (`entries`
    # is always homogeneous, one concrete type per call).
    for raw_entry, vec in zip(entries, entry_vecs, strict=True):
        entry = cast("LearningEntry | IssueEntry", raw_entry)
        by_scope.setdefault(entry.scope, []).append(vec)
        recurrence = getattr(entry, "recurrence", None)
        last_seen = getattr(entry, "last_seen", None)
        entry_rows.append(
            (
                entry.id,
                polarity,
                entry.scope,
                _pack(vec),
                recurrence,
                entry.title,
                entry.body,
                last_seen.isoformat() if last_seen is not None else None,
            )
        )
    for scope, vecs in by_scope.items():
        centroid = _centroid(vecs, dim)
        phrase = phrase_by_scope[scope]
        scope_rows.append((polarity, scope, _pack(centroid), _pack(phrase)))


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create the schema if this is a fresh file. ``IF NOT EXISTS``, not unconditional ``CREATE
    TABLE``: :func:`rebuild_index` now rewrites rows in the SAME persistent file across every
    rebuild (§ its docstring) instead of always starting from a brand-new one, so this must be
    idempotent."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS scopes (
            polarity TEXT NOT NULL,
            scope    TEXT NOT NULL,
            centroid BLOB NOT NULL,
            phrase   BLOB NOT NULL,
            PRIMARY KEY (polarity, scope)
        );
        CREATE TABLE IF NOT EXISTS entries (
            id         TEXT PRIMARY KEY,
            polarity   TEXT NOT NULL,
            scope      TEXT NOT NULL,
            vector     BLOB NOT NULL,
            recurrence INTEGER,
            title      TEXT NOT NULL,
            body       TEXT NOT NULL,
            last_seen  TEXT
        );
        """
    )


# --------------------------------------------------------------------------- ensure / query


def ensure_index(loc: StoreLocation, backend: EmbeddingBackend) -> None:
    """Rebuild the index if it is missing or stale, serialized against captures and other rebuilds.

    Takes the per-store write lock (the same one ``capture`` holds) so a rebuild triggered by
    ``recall`` never overlaps a capture's write or another rebuild.
    """
    with store_write_lock(loc):
        rebuild_index_if_stale(loc, backend)


def rebuild_index_if_stale(loc: StoreLocation, backend: EmbeddingBackend) -> None:
    """Rebuild the index iff missing or stale. Lock-free: call while already holding the write lock
    (as ``capture`` does) or via :func:`ensure_index` (which takes the lock for you)."""
    path = index_path(loc)
    if path.exists():
        try:
            conn = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_SECONDS)
            try:
                row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'fingerprint'"
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            row = None
        if row is not None and row[0] == _fingerprint(loc, backend):
            return
    rebuild_index(loc, backend)


def load_scopes(
    loc: StoreLocation, polarity: str, conn: sqlite3.Connection | None = None
) -> list[ScopeVectors]:
    """Every scope's centroid + phrase vectors for ``polarity``.

    Pass ``conn`` — already inside an explicit transaction, see ``retrieve()`` — to read from an
    already-open connection so several loads share ONE consistent snapshot (SQLite's own
    transaction isolation blocks a concurrent rebuild's commit until that transaction ends); when
    omitted this opens and closes its own single-statement connection.
    """
    close = conn is None
    if conn is None:
        conn = sqlite3.connect(str(index_path(loc)), timeout=BUSY_TIMEOUT_SECONDS)
    try:
        rows = conn.execute(
            "SELECT scope, centroid, phrase FROM scopes WHERE polarity = ?", (polarity,)
        ).fetchall()
    finally:
        if close:
            conn.close()
    return [
        ScopeVectors(scope, _unpack(centroid), _unpack(phrase))
        for scope, centroid, phrase in rows
    ]


def load_entries(
    loc: StoreLocation, polarity: str, conn: sqlite3.Connection | None = None
) -> list[IndexedEntry]:
    """Every entry (with its vector + surfaced fields) for ``polarity``.

    Pass ``conn`` to share one snapshot across loads (see :func:`load_scopes`); omitted opens its
    own connection.
    """
    close = conn is None
    if conn is None:
        conn = sqlite3.connect(str(index_path(loc)), timeout=BUSY_TIMEOUT_SECONDS)
    try:
        rows = conn.execute(
            "SELECT id, polarity, scope, vector, recurrence, title, body, last_seen "
            "FROM entries WHERE polarity = ?",
            (polarity,),
        ).fetchall()
    finally:
        if close:
            conn.close()
    return [
        IndexedEntry(
            id=row[0],
            polarity=row[1],
            scope=row[2],
            vector=_unpack(row[3]),
            recurrence=row[4],
            title=row[5],
            body=row[6],
            last_seen=row[7],
        )
        for row in rows
    ]
