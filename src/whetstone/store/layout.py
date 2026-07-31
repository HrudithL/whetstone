"""Per-skill store layout: resolution, lazy creation, git init/commit, and registry.

Each attached skill gets its own git-tracked store under the store root::

    <store-root>/<skill-slug>/
      learnings/   source of truth, grouped by scope
      issues/      source of truth, grouped by scope
      .git/        version history

A small ``registry.json`` at the store root (server metadata, outside any per-skill git repo)
records the attached skills. Store creation is *lazy* and idempotent: ``ensure_store`` can be called
by ``attach`` explicitly or by future ``recall``/``capture`` without an explicit attach.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from ..config import Config, load_config
from .slug import safe_component

try:  # POSIX file locking (macOS/Linux, the XDG target).
    import fcntl
except ImportError:  # pragma: no cover - exercised on Windows CI, not locally
    fcntl = None  # type: ignore[assignment]

try:  # Windows file locking.
    import msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX CI, not on Windows
    msvcrt = None  # type: ignore[assignment]

_REGISTRY_NAME = "registry.json"
# The reserved slug for the M5e learned global layer. It is used verbatim as both the "skill" name
# and the store directory, bypassing `skill_slug`/`safe_component` (which ALWAYS append a `-<hash>`
# suffix, so no real skill name can ever derive this bare literal — the collision the M5e plan calls
# out is structurally impossible). The global store is deliberately kept OUT of the registry so it
# is never reported as an attached skill by `metrics`; `recall` consults it by orchestration only.
GLOBAL_SLUG = "__global__"
# Only the markdown is source of truth. The sqlite index is derived/rebuildable and events.jsonl is
# local telemetry (§5.1), so a per-store .gitignore keeps both out of the committed history.
_STORE_GITIGNORE = "index.sqlite\nindex.sqlite-*\nevents.jsonl\ncompact-report.md\n"
# Applied per-command so a store commit never depends on (or mutates) the user's global git config:
# a fixed identity, no GPG signing, and no user hooks (a global core.hooksPath / template hook must
# not be able to fail Whetstone's internal bookkeeping commits). This disables hooks via config
# rather than the prohibited --no-verify flag.
_GIT_CONFIG = [
    "-c",
    "user.name=Whetstone",
    "-c",
    "user.email=whetstone@localhost",
    "-c",
    "commit.gpgsign=false",
    # os.devnull, not a hardcoded "/dev/null": that literal doesn't exist on Windows (which has
    # "nul" instead).
    "-c",
    f"core.hooksPath={os.devnull}",
]


@dataclass
class StoreLocation:
    """Where a skill's store lives and how it maps back to the skill."""

    skill: str
    slug: str
    path: Path

    @property
    def learnings_dir(self) -> Path:
        return self.path / "learnings"

    @property
    def issues_dir(self) -> Path:
        return self.path / "issues"


def resolve_store_root(config: Config | None = None) -> Path:
    """The store root, from config (which already applied env + TOML precedence)."""
    cfg = config if config is not None else load_config()
    return cfg.store_root


def skill_slug(skill: str) -> str:
    """A safe, bounded, collision-free directory component for a skill name.

    Uses :func:`safe_component` so two distinct skill names (e.g. ``a/b`` and ``ab``, or many
    non-ASCII names) can never resolve to the same store directory.
    """
    return safe_component(skill)


def store_location(skill: str, config: Config | None = None) -> StoreLocation:
    """Resolve where ``skill``'s store lives without creating anything.

    The reserved :data:`GLOBAL_SLUG` maps to itself (not through ``skill_slug``) so the M5e global
    layer gets a stable, un-hashed directory that no real skill's slug can collide with.
    """
    root = resolve_store_root(config)
    slug = GLOBAL_SLUG if skill == GLOBAL_SLUG else skill_slug(skill)
    return StoreLocation(skill=skill, slug=slug, path=root / slug)


def global_store_location(config: Config | None = None) -> StoreLocation:
    """The reserved global-layer store (§M5e). Same machinery as any per-skill store."""
    return store_location(GLOBAL_SLUG, config)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *_GIT_CONFIG, *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _ensure_store_gitignore(loc: StoreLocation) -> bool:
    """Write the per-store ``.gitignore`` if missing/outdated; return True iff the file changed."""
    path = loc.path / ".gitignore"
    if not path.exists() or path.read_text(encoding="utf-8") != _STORE_GITIGNORE:
        path.write_text(_STORE_GITIGNORE, encoding="utf-8")
        return True
    return False


@contextmanager
def store_write_lock(loc: StoreLocation) -> Iterator[None]:
    """Serialize all mutations of one store (and its index rebuilds) across calls and processes.

    ``capture`` runs its whole critical section — duplicate check, id allocation, markdown write,
    index rebuild, git commit — under this lock so concurrent captures for the same skill can't race
    on ``next_id`` (which would mint duplicate ids or drop entries) or interleave index rebuilds.
    ``recall``'s ``ensure_index`` takes the same lock, so a rebuild never overlaps another rebuild
    or a capture. The lock file sits in the store root (outside the per-skill git repo), so it is
    never committed. Real mutual exclusion on both POSIX (``fcntl``) and Windows (``msvcrt``).
    """
    with _file_lock(loc.path.parent / f".write-{loc.slug}.lock"):
        yield


@contextmanager
def store_events_lock(loc: StoreLocation) -> Iterator[None]:
    """Serialize appends to one store's ``events.jsonl`` across calls and processes.

    A whole-line append can take more than one ``os.write`` on a partial write; this lock keeps the
    fragments contiguous so a concurrent writer can't interleave a record between them. It is a
    *separate* lock file from :func:`store_write_lock`, so ``capture`` (which emits its event while
    holding the write lock) can take it without self-deadlock. Lock file sits in the store root
    (outside the per-skill git repo).
    """
    with _file_lock(loc.path.parent / f".events-{loc.slug}.lock"):
        yield


def commit_store(loc: StoreLocation, message: str) -> None:
    """Stage all tracked markdown changes and commit them to the store's git repo.

    Derived artifacts (``index.sqlite``, ``events.jsonl``) are excluded by the store ``.gitignore``,
    so ``git add -A`` only ever stages the source-of-truth markdown.
    """
    _git(["add", "-A"], cwd=loc.path)
    _git(["commit", "-q", "-m", message], cwd=loc.path)


def commit_paths(loc: StoreLocation, paths: list[str], message: str) -> None:
    """Commit ONLY the given paths, leaving any other working-tree changes untouched.

    Used for internal bookkeeping commits (e.g. a repaired ``.gitignore``) so a ``recall`` or
    ``attach`` can never sweep unrelated untracked/modified markdown into it. Staging then
    committing is scoped to ``paths``; if that stages no actual change, nothing is committed (no
    empty commits).
    """
    _git(["add", "--", *paths], cwd=loc.path)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", *paths],
        cwd=str(loc.path),
        capture_output=True,
        text=True,
    )
    if staged.returncode == 0:  # 0 == no staged diff for these paths
        return
    _git(["commit", "-q", "-m", message, "--", *paths], cwd=loc.path)


def _lock_exclusive(fh: IO[str]) -> None:
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_EX)
        return
    assert msvcrt is not None  # one of the two is always available (POSIX or Windows)
    # msvcrt.locking(LK_LOCK) retries internally for ~10s then raises OSError instead of blocking
    # indefinitely like fcntl.flock(LOCK_EX) — loop around it so contention just waits, matching
    # the POSIX side's semantics, rather than surfacing a spurious failure under real contention.
    while True:  # pragma: no cover - exercised on Windows CI, not on POSIX
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            return
        except OSError:
            continue


def _unlock(fh: IO[str]) -> None:
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_UN)
    else:  # pragma: no cover - exercised on Windows CI, not on POSIX
        assert msvcrt is not None
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    """Cross-call/cross-process mutual exclusion on ``lock_path`` — ``fcntl.flock`` on POSIX,
    ``msvcrt.locking`` on Windows.

    Used to serialize both store creation (the ``is_store`` check + ``git init``/commit) and the
    registry read-modify-write, so concurrent ``attach``/lazy-create calls can't race.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as fh:
        _lock_exclusive(fh)
        try:
            yield
        finally:
            _unlock(fh)


def is_store(path: Path) -> bool:
    """True if ``path`` is a *fully* initialized store: a git repo with a baseline commit.

    Checking ``HEAD`` (not just ``.git``) means a store left half-created by an interrupted
    ``ensure_store`` (``.git`` present but no commit yet) is treated as not-yet-a-store, so the next
    call finishes initialization instead of registering an empty repo.
    """
    if not (path / ".git").exists():
        return False
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@dataclass
class EnsureResult:
    """Outcome of :func:`ensure_store`."""

    location: StoreLocation
    created: bool


def ensure_store(skill: str, config: Config | None = None) -> EnsureResult:
    """Create the skill's store (dirs + git repo + initial commit) if absent; idempotent.

    Returns the location and whether it was newly created. Safe to call repeatedly and safe to
    call lazily from future ``recall``/``capture`` paths.
    """
    loc = store_location(skill, config)
    root = resolve_store_root(config)
    root.mkdir(parents=True, exist_ok=True)

    # Serialize check + create so two concurrent calls for the same skill can't both run
    # git init/commit in one directory (which races to exit 128/1). Double-checked: the winner
    # creates; the loser re-observes a finished store inside the lock and returns it as existing.
    with _file_lock(root / f".create-{loc.slug}.lock"):
        if is_store(loc.path):
            # Repair scaffolding: an existing store that lost its scope dirs (or predates the
            # derived index) still gets them back, so `attach`/lazy-create always leaves
            # learnings/, issues/, and the .gitignore present.
            loc.learnings_dir.mkdir(parents=True, exist_ok=True)
            loc.issues_dir.mkdir(parents=True, exist_ok=True)
            # An upgraded M0 store predates the .gitignore. If we just added/updated it, commit that
            # bookkeeping now (guarded on a real change, so no empty commits) so the repo isn't left
            # dirty for the next operation.
            if _ensure_store_gitignore(loc):
                commit_paths(loc, [".gitignore"], "Add derived-artifact .gitignore")
            if loc.slug != GLOBAL_SLUG:  # the global layer is never a registered skill (§M5e)
                _register(loc, config)
            return EnsureResult(location=loc, created=False)

        loc.learnings_dir.mkdir(parents=True, exist_ok=True)
        loc.issues_dir.mkdir(parents=True, exist_ok=True)
        # .gitkeep so the (initially empty) scope directories are tracked from the first commit.
        (loc.learnings_dir / ".gitkeep").write_text("", encoding="utf-8")
        (loc.issues_dir / ".gitkeep").write_text("", encoding="utf-8")
        _ensure_store_gitignore(loc)

        _git(["init", "-q"], cwd=loc.path)
        _git(["add", "-A"], cwd=loc.path)
        _git(["commit", "-q", "-m", f"Initialize Whetstone store for '{skill}'"], cwd=loc.path)

        if loc.slug != GLOBAL_SLUG:  # the global layer is never a registered skill (§M5e)
            _register(loc, config)
        return EnsureResult(location=loc, created=True)


# --------------------------------------------------------------------------- registry


def registry_path(config: Config | None = None) -> Path:
    return resolve_store_root(config) / _REGISTRY_NAME


def read_registry(config: Config | None = None) -> dict[str, dict]:
    path = registry_path(config)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def registry_write_lock(config: Config | None = None) -> Iterator[None]:
    """Serialize registry read-modify-writes across calls and processes.

    This is the SAME lock :func:`_register` takes to add a skill, exposed publicly so a caller
    that needs to *prevent* a new skill from being registered for a stretch of its own critical
    section — not just read a snapshot of the registry — can hold it too. `whetstone.promotion`'s
    ``promote_cluster`` is the first such caller: while it holds this lock, `_register` cannot
    complete, so a fresh :func:`read_registry` taken under it is authoritative for the whole span,
    not just the instant it was read.
    """
    with _file_lock(registry_path(config).parent / ".registry.lock"):
        yield


def _register(loc: StoreLocation, config: Config | None, skill_path: str | None = None) -> None:
    with registry_write_lock(config):
        path = registry_path(config)
        registry = read_registry(config)
        record = registry.get(loc.skill, {})
        record.update(
            {
                "slug": loc.slug,
                "path": str(loc.path),
                "attached_at": record.get("attached_at")
                or datetime.now(UTC).isoformat(timespec="seconds"),
            }
        )
        if skill_path is not None:
            record["skill_path"] = skill_path
        registry[loc.skill] = record
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)


def attach_skill(
    skill: str, skill_path: str | None = None, config: Config | None = None
) -> dict:
    """Attach ``skill``: ensure its store exists and record it in the registry. Idempotent.

    Returns a JSON-friendly summary describing the store and whether it was newly created.
    """
    if skill == GLOBAL_SLUG:
        raise ValueError(
            f"{GLOBAL_SLUG!r} is reserved for the Whetstone global layer and cannot be attached "
            "as a skill."
        )
    result = ensure_store(skill, config)
    _register(result.location, config, skill_path=skill_path)
    return {
        "skill": skill,
        "slug": result.location.slug,
        "path": str(result.location.path),
        "created": result.created,
        "status": "attached" if result.created else "already_attached",
    }
