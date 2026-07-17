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
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..config import Config, load_config
from .slug import safe_component

_REGISTRY_NAME = "registry.json"
# Commit identity + settings applied per-command so a store commit never depends on (or mutates)
# the user's global git config, and never blocks on GPG signing.
_GIT_CONFIG = [
    "-c",
    "user.name=Whetstone",
    "-c",
    "user.email=whetstone@localhost",
    "-c",
    "commit.gpgsign=false",
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
    """Resolve where ``skill``'s store lives without creating anything."""
    root = resolve_store_root(config)
    slug = skill_slug(skill)
    return StoreLocation(skill=skill, slug=slug, path=root / slug)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *_GIT_CONFIG, *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def is_store(path: Path) -> bool:
    """True if ``path`` is an initialized Whetstone store (has a git repo)."""
    return (path / ".git").exists()


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

    if is_store(loc.path):
        _register(loc, config)
        return EnsureResult(location=loc, created=False)

    loc.learnings_dir.mkdir(parents=True, exist_ok=True)
    loc.issues_dir.mkdir(parents=True, exist_ok=True)
    # .gitkeep so the (initially empty) scope directories are tracked from the first commit.
    (loc.learnings_dir / ".gitkeep").write_text("", encoding="utf-8")
    (loc.issues_dir / ".gitkeep").write_text("", encoding="utf-8")

    _git(["init", "-q"], cwd=loc.path)
    _git(["add", "-A"], cwd=loc.path)
    _git(["commit", "-q", "-m", f"Initialize Whetstone store for '{skill}'"], cwd=loc.path)

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


def _register(loc: StoreLocation, config: Config | None, skill_path: str | None = None) -> None:
    path = registry_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
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
    result = ensure_store(skill, config)
    _register(result.location, config, skill_path=skill_path)
    return {
        "skill": skill,
        "slug": result.location.slug,
        "path": str(result.location.path),
        "created": result.created,
        "status": "attached" if result.created else "already_attached",
    }
