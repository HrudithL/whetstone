"""M5e — the learned global layer: recall union, promotion, the reserved slug, the toggle."""

from __future__ import annotations

import pytest

from conftest import make_learning, seed
from whetstone import server
from whetstone.config import load_config
from whetstone.embeddings import get_backend
from whetstone.promotion import promote_to_global
from whetstone.server import attach, capture, recall
from whetstone.store import index
from whetstone.store.access import find_learning, load_issues, load_learnings
from whetstone.store.layout import (
    GLOBAL_SLUG,
    attach_skill,
    ensure_store,
    global_store_location,
    store_location,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point the server's own load_config() at a temp store root."""
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    return tmp_path


def _seed_global(learnings=(), issues=()):
    """Seed the reserved global store's markdown directly and (re)build its index."""
    config = load_config()
    ensure_store(GLOBAL_SLUG, config)
    g_loc = global_store_location(config)
    seed(g_loc, learnings=learnings, issues=issues)
    index.rebuild_index(g_loc, get_backend(config))
    return g_loc


# --------------------------------------------------------------------------- recall union


def test_recall_unions_skill_and_global_origin_tagged(env):
    capture("gt", "learning", "Right-align currency columns.", "currency columns", "prov")
    _seed_global(learnings=[make_learning("L1", "Prefer muted palettes everywhere.", "palette")])

    result = recall("gt", "styling a table: currency columns, color palette")

    origins = {x["origin"] for x in result["learnings"]}
    assert origins == {"skill", "global"}
    skill_rules = [x["rule"] for x in result["learnings"] if x["origin"] == "skill"]
    global_rules = [x["rule"] for x in result["learnings"] if x["origin"] == "global"]
    assert any("currency" in r for r in skill_rules)
    assert any("muted palettes" in r for r in global_rules)


def test_recall_consult_global_false_is_pure_per_skill(env, monkeypatch):
    capture("gt", "learning", "Right-align currency columns.", "currency columns", "prov")
    _seed_global(learnings=[make_learning("L1", "Prefer muted palettes everywhere.", "palette")])

    monkeypatch.setenv("WHETSTONE_CONSULT_GLOBAL", "false")
    result = recall("gt", "styling a table: currency columns, color palette")

    assert all(x["origin"] == "skill" for x in result["learnings"])
    assert all("muted palettes" not in x["rule"] for x in result["learnings"])


def test_retrieve_called_once_per_consulted_store(env, monkeypatch):
    """The retrieval FUNCTION is reused verbatim (once per store), not rewritten (§M5e)."""
    capture("gt", "learning", "Right-align currency columns.", "currency columns", "prov")
    _seed_global(learnings=[make_learning("L1", "Prefer muted palettes.", "palette")])

    calls = []
    real = server.retrieve

    def spy(loc, *a, **k):
        calls.append(loc.slug)
        return real(loc, *a, **k)

    monkeypatch.setattr(server, "retrieve", spy)
    recall("gt", "table styling with a color palette")
    assert len(calls) == 2
    assert GLOBAL_SLUG in calls

    calls.clear()
    monkeypatch.setenv("WHETSTONE_CONSULT_GLOBAL", "false")
    recall("gt", "table styling with a color palette")
    assert calls == [store_location("gt").slug]


# --------------------------------------------------------------------------- promotion


def test_promote_writes_global_and_retires_source(env):
    res = capture("gt", "learning", "Prefer muted palettes everywhere.", "palette", "prov")
    source_id = res["entry_id"]

    out = promote_to_global("gt", source_id)

    assert out["polarity"] == "learning"
    assert out["global_id"].startswith("L")
    # Source copy is gone from the skill store.
    assert find_learning(store_location("gt"), source_id) is None
    # A copy now lives in the global store under a re-minted id.
    g_loc = global_store_location(load_config())
    g_learnings = load_learnings(g_loc)
    assert len(g_learnings) == 1
    assert g_learnings[0].id == out["global_id"]
    assert "muted palettes" in g_learnings[0].body
    assert "promoted from gt" in g_learnings[0].provenance


def test_promote_issue_into_global(env):
    res = capture("gt", "issue", "Never band tables under ten rows.", "small tables", "prov")
    out = promote_to_global("gt", res["entry_id"])
    assert out["polarity"] == "issue"
    g_loc = global_store_location(load_config())
    assert [i.id for i in load_issues(g_loc)] == [out["global_id"]]


def test_promoted_global_learning_surfaces_on_recall(env):
    res = capture("web", "learning", "Prefer muted palettes everywhere.", "palette", "prov")
    promote_to_global("web", res["entry_id"])

    # A DIFFERENT skill now sees the promoted preference via the global layer.
    result = recall("gt", "color palette choices for a component")
    assert any(
        x["origin"] == "global" and "muted palettes" in x["rule"] for x in result["learnings"]
    )


# --------------------------------------------------------------------------- reserved slug


def test_global_slug_cannot_collide_with_real_skill(env):
    # A real skill literally named "__global__" (or "global") never resolves to the bare reserved
    # slug — safe_component always appends a hash suffix.
    assert store_location("global").slug != GLOBAL_SLUG
    assert store_location("__global__ hi there").slug != GLOBAL_SLUG


def test_attach_rejects_reserved_slug(env):
    with pytest.raises(ValueError, match="reserved"):
        attach_skill(GLOBAL_SLUG)
    with pytest.raises(ValueError, match="reserved"):
        attach(GLOBAL_SLUG)


def test_global_store_not_in_registry(env):
    from whetstone.store.layout import read_registry

    capture("gt", "learning", "Prefer muted palettes.", "palette", "prov")
    promote_to_global("gt", "L1")
    # Promotion created the global store, but it is never registered as an attached skill.
    assert GLOBAL_SLUG not in read_registry(load_config())
