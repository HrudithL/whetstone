"""Security, determinism, collision, and length tests for scope/skill -> filename derivation."""

from __future__ import annotations

from pathlib import Path

import pytest

from whetstone.store import base_slug, safe_component, scope_filename


@pytest.mark.parametrize(
    "value",
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
def test_component_cannot_escape_directory(value, tmp_path):
    component = safe_component(value)
    assert "/" not in component
    assert "\\" not in component
    assert ".." not in component
    # Resolving the component under a base dir must stay inside that base dir.
    base = tmp_path / "learnings"
    base.mkdir()
    resolved = (base / f"{component}.md").resolve()
    assert base.resolve() == Path(resolved).parent


def test_base_slug_basic_shape():
    assert base_slug("Currency Columns") == "currency-columns"
    assert base_slug("  Color  Palette  ") == "color-palette"
    assert base_slug("") == "scope"


def test_component_is_deterministic_and_order_independent():
    # Same input -> same output, no matter what else has been created before.
    assert safe_component("currency columns") == safe_component("currency columns")
    assert scope_filename("a/b") == scope_filename("a/b")


def test_distinct_colliding_scopes_map_to_distinct_files():
    # "a/b" and "ab" share a base stem, but the full-string hash keeps their files distinct
    # regardless of creation order (no persisted mapping needed).
    assert base_slug("a/b") == base_slug("ab") == "ab"
    assert scope_filename("a/b") != scope_filename("ab")
    for name in (scope_filename("a/b"), scope_filename("ab")):
        assert name.startswith("ab-") and name.endswith(".md")


def test_component_is_length_bounded():
    # A long but otherwise safe scope must not produce an over-long path component (ENAMETOOLONG).
    long_scope = "x" * 300
    component = safe_component(long_scope)
    assert len(component) <= 80  # 60-char stem cap + "-" + 8-char hash, comfortably under FS limits
    # Distinct long scopes sharing the truncated prefix still map to distinct files via the hash.
    assert safe_component("x" * 300) != safe_component("x" * 300 + "-different-tail")


def test_scope_filename_has_md_extension():
    assert scope_filename("color palette").endswith(".md")
