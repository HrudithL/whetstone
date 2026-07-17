"""Scope -> filename slugging (SECURITY-CRITICAL, see LEARNING_SKILLS_DESIGN.md §5.1).

A scope phrase is model-/user-supplied, so its slug MUST NOT be able to write outside the
``learnings/`` or ``issues/`` directory. We lowercase, turn spaces into hyphens, and strip path
separators and ``..`` so the result is always a single safe filename component. When two *distinct*
scopes slug to the same name (e.g. ``a/b`` and ``ab``), a short hash suffix disambiguates so the
file <-> scope mapping stays 1:1.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

_UNSAFE = re.compile(r"[^a-z0-9_-]+")
_HYPHENS = re.compile(r"-{2,}")


def base_slug(scope: str) -> str:
    """Slug a scope phrase to a single safe filename stem (no extension, no separators)."""
    s = scope.strip().lower()
    s = s.replace("..", "")  # strip parent refs
    s = s.replace("/", "").replace("\\", "")  # strip path separators
    s = s.replace(" ", "-")  # spaces -> hyphen
    s = _UNSAFE.sub("-", s)  # anything else -> hyphen
    s = _HYPHENS.sub("-", s).strip("-_")
    return s or "scope"


def _hash_suffix(scope: str) -> str:
    return hashlib.sha1(scope.encode("utf-8")).hexdigest()[:8]


def scope_filename(scope: str, existing_scopes: Iterable[str] = ()) -> str:
    """Return the ``<slug>.md`` filename for ``scope``.

    ``existing_scopes`` is the set of other scope phrases already assigned files in the same
    directory. If a *distinct* existing scope already claims this base slug, a short hash suffix is
    appended so the mapping stays 1:1.
    """
    base = base_slug(scope)
    for other in existing_scopes:
        if other != scope and base_slug(other) == base:
            return f"{base}-{_hash_suffix(scope)}.md"
    return f"{base}.md"
