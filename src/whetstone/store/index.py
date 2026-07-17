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

from ..embeddings import EmbeddingBackend
from .access import load_issues, load_learnings
from .entries import IssueEntry, LearningEntry
from .layout import StoreLocation

INDEX_NAME = "index.sqlite"


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


def _fingerprint(loc: StoreLocation, backend: EmbeddingBackend) -> str:
    """A hash of the markdown plus backend identity; changes iff the index would differ."""
    hasher = hashlib.sha1()
    hasher.update(f"{type(backend).__name__}:{backend.dim}\0".encode())
    for directory in (loc.learnings_dir, loc.issues_dir):
        for path in sorted(directory.glob("*.md")):
            hasher.update(path.name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
            hasher.update(b"\0")
    return hasher.hexdigest()


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
    """Regenerate ``index.sqlite`` from the markdown store (fully idempotent)."""
    learnings = load_learnings(loc)
    issues = load_issues(loc)

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
    entry_rows: list[tuple[str, str, str, bytes, int | None, str, str]] = []

    _collect(
        "learning", learnings, learn_vecs, learn_phrase, dim, scope_rows, entry_rows
    )
    _collect("issue", issues, issue_vecs, issue_phrase, dim, scope_rows, entry_rows)

    path = index_path(loc)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".sqlite.tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    try:
        _create_schema(conn)
        conn.executemany(
            "INSERT INTO scopes (polarity, scope, centroid, phrase) VALUES (?, ?, ?, ?)",
            scope_rows,
        )
        conn.executemany(
            "INSERT INTO entries (id, polarity, scope, vector, recurrence, title, body) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            entry_rows,
        )
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('fingerprint', ?)",
            (_fingerprint(loc, backend),),
        )
        conn.commit()
    finally:
        conn.close()
    path.unlink(missing_ok=True)
    tmp.replace(path)


def _collect(
    polarity: str,
    entries: list[LearningEntry] | list[IssueEntry],
    entry_vecs: list[list[float]],
    phrase_by_scope: dict[str, list[float]],
    dim: int,
    scope_rows: list[tuple[str, str, bytes, bytes]],
    entry_rows: list[tuple[str, str, str, bytes, int | None, str, str]],
) -> None:
    by_scope: dict[str, list[list[float]]] = {}
    for entry, vec in zip(entries, entry_vecs, strict=True):
        by_scope.setdefault(entry.scope, []).append(vec)
        recurrence = getattr(entry, "recurrence", None)
        entry_rows.append(
            (entry.id, polarity, entry.scope, _pack(vec), recurrence, entry.title, entry.body)
        )
    for scope, vecs in by_scope.items():
        centroid = _centroid(vecs, dim)
        phrase = phrase_by_scope[scope]
        scope_rows.append((polarity, scope, _pack(centroid), _pack(phrase)))


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE scopes (
            polarity TEXT NOT NULL,
            scope    TEXT NOT NULL,
            centroid BLOB NOT NULL,
            phrase   BLOB NOT NULL,
            PRIMARY KEY (polarity, scope)
        );
        CREATE TABLE entries (
            id         TEXT PRIMARY KEY,
            polarity   TEXT NOT NULL,
            scope      TEXT NOT NULL,
            vector     BLOB NOT NULL,
            recurrence INTEGER,
            title      TEXT NOT NULL,
            body       TEXT NOT NULL
        );
        """
    )


# --------------------------------------------------------------------------- ensure / query


def ensure_index(loc: StoreLocation, backend: EmbeddingBackend) -> None:
    """Rebuild the index if it is missing or stale relative to the markdown + backend."""
    path = index_path(loc)
    if path.exists():
        try:
            conn = sqlite3.connect(str(path))
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


def load_scopes(loc: StoreLocation, polarity: str) -> list[ScopeVectors]:
    """Every scope's centroid + phrase vectors for ``polarity``."""
    conn = sqlite3.connect(str(index_path(loc)))
    try:
        rows = conn.execute(
            "SELECT scope, centroid, phrase FROM scopes WHERE polarity = ?", (polarity,)
        ).fetchall()
    finally:
        conn.close()
    return [
        ScopeVectors(scope, _unpack(centroid), _unpack(phrase))
        for scope, centroid, phrase in rows
    ]


def load_entries(loc: StoreLocation, polarity: str) -> list[IndexedEntry]:
    """Every entry (with its vector + surfaced fields) for ``polarity``."""
    conn = sqlite3.connect(str(index_path(loc)))
    try:
        rows = conn.execute(
            "SELECT id, polarity, scope, vector, recurrence, title, body "
            "FROM entries WHERE polarity = ?",
            (polarity,),
        ).fetchall()
    finally:
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
        )
        for row in rows
    ]
