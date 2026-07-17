"""Deriving safe filesystem names from scope/skill strings (SECURITY-CRITICAL, §5.1).

Scope phrases and skill names are model-/user-supplied, so the name we derive MUST be:

- **contained** — never able to escape ``learnings/``/``issues/`` or the store root (no path
  separators, no ``..``);
- **bounded** — short enough that the resulting path is accepted by common filesystems
  (long prose scopes must not raise ``ENAMETOOLONG``);
- **deterministic & collision-free** — the same string always maps to the same component, and two
  *distinct* strings never map to the same one, independent of call order or what else exists.

We satisfy all three by combining a readable, bounded slug with a short hash of the *full* original
string: ``<slug>-<hash>``. Always suffixing the hash (not only "on collision") is what makes the
mapping order-independent and needs no persisted lookup table — the readable ``scope:`` phrase still
lives inside each block for humans.
"""

from __future__ import annotations

import hashlib
import re

_UNSAFE = re.compile(r"[^a-z0-9_-]+")
_HYPHENS = re.compile(r"-{2,}")
_MAX_STEM = 60  # readable portion cap; final component stays well under filesystem limits


def normalize_scope(scope: str) -> str:
    """Canonical form of a scope phrase: strip ends and collapse internal whitespace/newlines to
    single spaces.

    Applied at the tool boundary so the SAME string is used for the filename hash, the stored
    ``scope:`` field, and the dedup embedding. Without it, a scope with stray whitespace/newlines
    would hash to one filename while the markdown writer stored a normalized ``scope:`` — a later
    lookup with the clean scope would compute a different filename and miss the entry.
    """
    return " ".join(scope.split())


def base_slug(value: str) -> str:
    """Readable, bounded, single safe component (no extension, no separators, no ``..``)."""
    s = value.strip().lower()
    s = s.replace("..", "")  # strip parent refs
    s = s.replace("/", "").replace("\\", "")  # strip path separators
    s = s.replace(" ", "-")  # spaces -> hyphen
    s = _UNSAFE.sub("-", s)  # anything else -> hyphen
    s = _HYPHENS.sub("-", s).strip("-_")
    return (s[:_MAX_STEM].strip("-_")) or "scope"


def _hash(value: str) -> str:
    # 64 bits: distinct values that share the bounded stem still get distinct components with an
    # astronomically small collision probability at any realistic store size.
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def safe_component(value: str) -> str:
    """Deterministic, bounded, collision-resistant filesystem component for ``value``.

    Always ``<bounded-slug>-<hash(full value)>`` so distinct values never collide and the mapping
    never depends on call order or existing files.
    """
    return f"{base_slug(value)}-{_hash(value)}"


def scope_filename(scope: str) -> str:
    """The ``<component>.md`` filename that stores ``scope``."""
    return f"{safe_component(scope)}.md"
