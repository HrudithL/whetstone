"""Security and collision tests for scope -> filename slugging."""

from __future__ import annotations

from pathlib import Path

import pytest

from whetstone.store import base_slug, scope_filename


@pytest.mark.parametrize(
    "scope",
    [
        "../../etc/passwd",
        "..",
        "../secrets",
        "a/b/c",
        "a\\b\\c",
        "/absolute/path",
        "..\\..\\windows",
        "....//....//",
    ],
)
def test_slug_cannot_escape_directory(scope, tmp_path):
    slug = base_slug(scope)
    assert "/" not in slug
    assert "\\" not in slug
    assert ".." not in slug
    # Resolving the slug under a base dir must stay inside that base dir.
    base = tmp_path / "learnings"
    base.mkdir()
    resolved = (base / f"{slug}.md").resolve()
    assert base.resolve() == Path(resolved).parent


def test_slug_basic_shape():
    assert base_slug("Currency Columns") == "currency-columns"
    assert base_slug("  Color  Palette  ") == "color-palette"
    assert base_slug("") == "scope"


def test_distinct_scopes_that_collide_get_hash_suffix():
    # "a/b" strips to "ab", colliding with the literal scope "ab" (the doc's example).
    assert base_slug("a/b") == base_slug("ab") == "ab"
    # The first scope to claim the base stem keeps it; the later distinct collision is suffixed,
    # keeping the file <-> scope mapping 1:1.
    first = scope_filename("a/b", existing_scopes=[])
    second = scope_filename("ab", existing_scopes=["a/b"])
    assert first == "ab.md"
    assert second != "ab.md"
    assert second.startswith("ab-") and second.endswith(".md")
    assert first != second


def test_same_scope_is_not_treated_as_collision():
    # Passing the same scope in existing_scopes must not trigger a suffix.
    assert scope_filename("currency columns", existing_scopes=["currency columns"]) == (
        "currency-columns.md"
    )


def test_no_collision_returns_plain_stem():
    assert scope_filename("color palette", existing_scopes=["formatting"]) == "color-palette.md"
