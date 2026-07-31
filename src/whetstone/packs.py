"""Preference packs — export/import a curated set of learnings + issues (§M5c).

Extends "your preferences, in a git repo you own" to **sharing**: ``whetstone export <skill>``
writes a ``.tar.gz`` **preference pack** (the ``learnings/`` + ``issues/`` markdown plus a
``pack.toml`` manifest); ``whetstone import <skill> <pack>`` folds it into a store, dedup- and
conflict-aware. It is a CLI action, never an MCP tool — sharing is a deliberate human act; an agent
must not auto-import someone else's taste.

**Excluded from a pack:** ``events.jsonl`` (private telemetry), ``index.sqlite`` (derived), ``.git``
(a pack is a clean snapshot, not history), ``next_ids.json`` / ``compact-report.md`` (local state).

**Import re-mints every id** from the target store's own counter — a foreign id is never trusted
(the id-reuse hazard the metrics module already guards against). ``--merge`` (default) runs the same
dedup + conflict checks ``capture`` does: a near-duplicate folds in (recurrence summed, dates
widened, ``last_seen`` reset to import time for a fair decay start), an opposite-polarity clash is
**surfaced, not silently applied**. ``--replace`` wipes the target's markdown first, then imports
wholesale (still re-minting ids). Either way it commits once and emits an ``import`` event.
"""

from __future__ import annotations

import io
import tarfile
import tempfile
import tomllib
from dataclasses import replace
from datetime import UTC, date, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import Config, load_config
from .embeddings import EmbeddingBackend, get_backend
from .server import _find_conflict, _find_duplicate, _find_issue_conflict
from .store import index
from .store.access import (
    find_learning,
    load_issues,
    load_learnings,
    next_id,
    record_id,
    save_issue,
    save_learning,
)
from .store.entries import IssueEntry, LearningEntry
from .store.index import entry_text
from .store.layout import (
    StoreLocation,
    commit_store,
    ensure_store,
    store_location,
    store_write_lock,
)
from .telemetry import emit_import

_MANIFEST = "pack.toml"


def _whetstone_version() -> str:
    try:
        return version("whetstone-mcp")
    except PackageNotFoundError:  # pragma: no cover - only when not installed
        return "0+unknown"


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


# --------------------------------------------------------------------------- export


def export_pack(skill: str, out: str | Path | None = None, config: Config | None = None) -> dict:
    """Write a preference pack for ``skill`` to ``out`` (default ``<slug>-whetstone-pack.tar.gz`` in
    the cwd); return a summary. Only the markdown + a ``pack.toml`` manifest go in."""
    if config is None:
        config = load_config()
    ensure_store(skill, config)
    loc = store_location(skill, config)

    learnings = load_learnings(loc)
    issues = load_issues(loc)
    scopes = sorted({e.scope for e in learnings} | {e.scope for e in issues})
    manifest = _render_manifest(skill, loc.slug, learnings, issues, scopes)

    out_path = Path(out) if out is not None else Path.cwd() / f"{loc.slug}-whetstone-pack.tar.gz"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with store_write_lock(loc):  # a stable snapshot: no capture/compact mutating mid-archive
        with tarfile.open(out_path, "w:gz") as tar:
            for sub in ("learnings", "issues"):
                for md in sorted((loc.path / sub).glob("*.md")):
                    tar.add(md, arcname=f"{sub}/{md.name}")
            info = tarfile.TarInfo(_MANIFEST)
            data = manifest.encode("utf-8")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    return {
        "skill": skill,
        "slug": loc.slug,
        "path": str(out_path),
        "learnings": len(learnings),
        "issues": len(issues),
        "scopes": scopes,
    }


def _render_manifest(
    skill: str,
    slug: str,
    learnings: list[LearningEntry],
    issues: list[IssueEntry],
    scopes: list[str],
) -> str:
    scope_list = ", ".join(f'"{_toml_escape(s)}"' for s in scopes)
    return (
        f'skill = "{_toml_escape(skill)}"\n'
        f'slug = "{_toml_escape(slug)}"\n'
        f'whetstone_version = "{_whetstone_version()}"\n'
        f'created = "{datetime.now(UTC).isoformat(timespec="seconds")}"\n'
        f"learnings = {len(learnings)}\n"
        f"issues = {len(issues)}\n"
        f"scopes = [{scope_list}]\n"
    )


# --------------------------------------------------------------------------- import


def import_pack(
    skill: str,
    pack: str | Path,
    mode: str = "merge",
    config: Config | None = None,
    today: date | None = None,
) -> dict:
    """Import a preference pack into ``skill``'s store. ``mode`` is ``merge`` (default; dedup- and
    conflict-aware) or ``replace`` (wipe then import wholesale). Ids are always re-minted."""
    if mode not in ("merge", "replace"):
        raise ValueError(f"mode must be 'merge' or 'replace', got {mode!r}")
    if config is None:
        config = load_config()
    if today is None:
        today = datetime.now(UTC).date()
    pack_path = Path(pack)
    if not pack_path.exists():
        raise FileNotFoundError(f"no pack at {pack_path}")

    ensure_store(skill, config)
    loc = store_location(skill, config)
    backend = get_backend(config)

    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(pack_path, "r:gz") as tar:
            # filter="data" (3.12) blocks path traversal / absolute members from an untrusted pack.
            tar.extractall(tmp, filter="data")
        src = StoreLocation(skill="__pack__", slug="__pack__", path=Path(tmp))
        (src.path / "learnings").mkdir(exist_ok=True)
        (src.path / "issues").mkdir(exist_ok=True)
        incoming_learnings = load_learnings(src)
        incoming_issues = load_issues(src)

        with store_write_lock(loc):
            wiped = _wipe(loc) if mode == "replace" else 0
            index.rebuild_index(loc, backend)

            committed = merged = conflicts = 0
            for entry in incoming_learnings:
                outcome = _import_one(loc, backend, config, entry, "learning", today, mode)
                committed += outcome == "committed"
                merged += outcome == "merged"
                conflicts += outcome == "conflict"
                if outcome in ("committed", "merged"):
                    index.rebuild_index(loc, backend)  # keep dedup fresh for the next entry
            for issue_entry in incoming_issues:
                outcome = _import_one(loc, backend, config, issue_entry, "issue", today, mode)
                committed += outcome == "committed"
                merged += outcome == "merged"
                conflicts += outcome == "conflict"
                if outcome in ("committed", "merged"):
                    index.rebuild_index(loc, backend)

            # Commit + log only when the store actually changed (a merge that only surfaced
            # conflicts, or a replace that wiped nothing and imported nothing, leaves no diff — an
            # empty git commit would fail, mirroring compaction's no-op behavior).
            if committed or merged or wiped:
                index.rebuild_index(loc, backend)
                commit_store(loc, f"import: {pack_path.name} ({mode})")
                emit_import(
                    loc,
                    pack=pack_path.name,
                    mode=mode,
                    committed=committed,
                    merged=merged,
                    conflicts=conflicts,
                )

    return {
        "skill": skill,
        "pack": pack_path.name,
        "mode": mode,
        "committed": committed,
        "merged": merged,
        "conflicts": conflicts,
    }


def _wipe(loc: StoreLocation) -> int:
    """Remove all entry markdown (``--replace``), leaving the tracked ``.gitkeep`` so the empty
    scope dirs survive; return how many files were removed. ``next_ids.json`` is deliberately kept,
    so re-minted ids never reuse a past number."""
    removed = 0
    for sub in ("learnings", "issues"):
        for md in (loc.path / sub).glob("*.md"):
            md.unlink()
            removed += 1
    return removed


def _import_one(
    loc: StoreLocation,
    backend: EmbeddingBackend,
    config: Config,
    incoming: LearningEntry | IssueEntry,
    polarity: str,
    today: date,
    mode: str,
) -> str:
    """Import one incoming entry; return ``committed``/``merged``/``conflict``/``noop``.

    ``replace`` mode skips dedup/conflict (the store was just wiped) and writes a fresh, re-minted
    entry. ``merge`` mode reuses ``capture``'s dedup + conflict detectors: a near-duplicate folds
    in, an opposite-polarity clash is surfaced (not applied)."""
    scope = incoming.scope  # markdown stores the already-normalized scope
    vec = backend.embed([entry_text(incoming.title, incoming.body)])[0]
    scope_vec = backend.embed([scope])[0]

    if mode == "merge":
        duplicate = _find_duplicate(loc, polarity, scope, vec, scope_vec, config)
        if duplicate is not None:
            if isinstance(incoming, LearningEntry):
                existing = find_learning(loc, duplicate.id)
                # `duplicate.id` was just found in this store's index under the held write lock, so
                # the entry it names cannot have been concurrently removed — always present.
                assert existing is not None
                save_learning(
                    loc,
                    replace(
                        existing,
                        recurrence=existing.recurrence + incoming.recurrence,
                        first_seen=min(existing.first_seen, incoming.first_seen),
                        last_seen=today,  # fresh decay start for the folded-in preference
                    ),
                )
                return "merged"
            return "noop"  # a duplicate issue has nothing to fold (issues have no recurrence)
        conflict = _find_conflict(
            loc, polarity, scope, incoming.title, incoming.body, vec, scope_vec, config
        )
        if conflict is None and polarity == "issue":
            conflict = _find_issue_conflict(
                loc, scope, incoming.title, incoming.body, vec, scope_vec, config
            )
        if conflict is not None:
            return "conflict"

    new_id = next_id(loc, polarity)
    if isinstance(incoming, LearningEntry):
        save_learning(loc, replace(incoming, id=new_id, last_seen=today))
    else:
        save_issue(loc, replace(incoming, id=new_id))
    record_id(loc, new_id)
    return "committed"


def read_manifest(pack: str | Path) -> dict:
    """Read a pack's ``pack.toml`` manifest without importing it."""
    with tarfile.open(Path(pack), "r:gz") as tar:
        member = tar.extractfile(_MANIFEST)
        if member is None:
            raise ValueError(f"{pack} is missing {_MANIFEST}")
        return tomllib.loads(member.read().decode("utf-8"))
