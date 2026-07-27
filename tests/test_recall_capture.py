"""End-to-end tests for the recall + capture tools via their tool functions."""

from __future__ import annotations

import subprocess

import pytest

from conftest import make_issue, make_learning, seed
from whetstone.config import load_config
from whetstone.embeddings import get_backend
from whetstone.server import capture, recall
from whetstone.store import index
from whetstone.store.layout import GLOBAL_SLUG, ensure_store, global_store_location, store_location


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point the server's own load_config() at a temp store root."""
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    return tmp_path


def _commit_count(root, slug) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(root / slug),
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


# --------------------------------------------------------------------------- recall


def test_recall_payload_shape_matches_spec(env):
    capture(
        "gt",
        "learning",
        "Right-align currency columns and drop vertical gridlines.",
        "currency columns",
        "prov",
    )
    capture("gt", "issue", "Never band tables under ten rows.", "small tables", "prov")

    result = recall(
        "gt", "right-align the currency columns and never band small tables under ten rows"
    )

    assert set(result) == {
        "skill",
        "run_id",
        "learnings",
        "issues",
        "how_to_use",
        "capture_contract",
        "conflicts",
    }
    assert result["skill"] == "gt"
    assert result["run_id"].startswith("r-")
    assert "MANDATORY" in result["how_to_use"]
    assert "run_id" in result["capture_contract"]

    assert result["learnings"], "the currency learning should be recalled"
    learning = result["learnings"][0]
    assert set(learning) == {"id", "rule", "scope", "recurrence", "weight", "origin"}
    assert learning["origin"] == "skill"
    issue = result["issues"][0]
    assert set(issue) == {"id", "rule", "scope", "origin"}
    assert issue["origin"] == "skill"
    # Neither entry here forbids what the other affirms (different scopes) -> no conflict.
    assert result["conflicts"] == []


def test_recall_on_empty_store_returns_empty_lists(env):
    result = recall("fresh-skill", "some elaborated intent about tables")
    assert result["learnings"] == []
    assert result["issues"] == []
    assert result["run_id"].startswith("r-")


def test_recall_creates_store_lazily(env):
    recall("never-attached", "an elaborated intent")
    slug = store_location("never-attached").slug
    assert (env / slug / ".git").is_dir()


# --------------------------------------------------------------------------- conflicts (§M7b)


def test_recall_surfaces_a_conflict_between_co_returned_learning_and_issue(env):
    """A learning and an issue that clash — same pattern as test_capture_conflict.py's fixture —
    both end up in the returned set (seeded directly so `capture`'s own write-time conflict check,
    which would otherwise refuse the second one, never runs), and `recall`'s post-union pass must
    flag the pair.
    """
    capture("gt", "issue", "Never right-align the currency columns.", "currency columns", "prov")

    loc = store_location("gt")
    config = load_config()
    learning = make_learning("L1", "Right-align the currency columns.", "currency columns")
    seed(loc, learnings=[learning])
    index.rebuild_index(loc, get_backend(config))

    result = recall("gt", "right-align the currency columns")

    learning_ids = {x["id"] for x in result["learnings"]}
    issue_ids = {x["id"] for x in result["issues"]}
    assert "L1" in learning_ids, "the conflicting learning should be in the returned set"
    assert "I1" in issue_ids, "the conflicting issue should be in the returned set"

    assert result["conflicts"] == [
        {
            "a": "L1",
            "a_origin": "skill",
            "b": "I1",
            "b_origin": "skill",
            "note": result["conflicts"][0]["note"],
        }
    ]
    assert result["conflicts"][0]["note"]  # a non-empty human-readable explanation


def test_recall_conflicts_is_empty_for_a_clean_returned_set(env):
    # A learning and an issue in unrelated scopes -> no tension, `conflicts` stays [].
    capture("gt", "learning", "Prefer a serif typeface for captions.", "typography", "prov")
    capture("gt", "issue", "Never band tables under ten rows.", "small tables", "prov")

    result = recall("gt", "caption typography and row banding for small tables")

    assert result["learnings"]
    assert result["issues"]
    assert result["conflicts"] == []


def test_recall_does_not_flag_similarly_worded_entries_in_unrelated_scopes(env, monkeypatch):
    # Lower the cutoff so body-vector similarity ALONE would trigger a false conflict without the
    # scope-overlap gate (§7's `_find_conflict` requires it too) -- e.g. a "green checkmark for
    # successful transactions" learning and a "never green checkmark for error banners" issue read
    # as similar text, but apply to genuinely different, unrelated contexts.
    monkeypatch.setenv("WHETSTONE_CONFLICT_SIMILARITY", "0.1")
    capture(
        "gt",
        "learning",
        "Show a green checkmark icon for successful transactions.",
        "successful transactions",
        "prov",
    )
    loc = store_location("gt")
    config = load_config()
    seed(
        loc,
        issues=[
            make_issue(
                "I1",
                "Never show a green checkmark icon for error banners.",
                "error banners",
            )
        ],
    )
    index.rebuild_index(loc, get_backend(config))

    result = recall("gt", "green checkmark icon for successful transactions and error banners")

    assert "L1" in {x["id"] for x in result["learnings"]}
    assert "I1" in {x["id"] for x in result["issues"]}
    assert result["conflicts"] == []


def test_recall_conflict_ids_disambiguate_skill_and_global_origin(env):
    # The skill store and the global store mint ids from independent counters, so a skill-origin
    # L1/I1 conflict pair and a global-origin L1/I1 conflict pair can coexist with identical bare
    # ids -- `a_origin`/`b_origin` must disambiguate which physical entries each conflict names.
    capture("gt", "issue", "Never right-align the currency columns.", "currency columns", "prov")
    loc = store_location("gt")
    config = load_config()
    backend = get_backend(config)
    skill_learning = make_learning("L1", "Right-align the currency columns.", "currency columns")
    seed(loc, learnings=[skill_learning])
    index.rebuild_index(loc, backend)

    g_config = load_config()
    ensure_store(GLOBAL_SLUG, g_config)
    g_loc = global_store_location(g_config)
    seed(
        g_loc,
        learnings=[make_learning("L1", "Use bold section headers.", "section headers")],
        issues=[make_issue("I1", "Never use bold section headers.", "section headers")],
    )
    index.rebuild_index(g_loc, backend)

    result = recall(
        "gt", "right-align the currency columns and bold section headers styling"
    )

    pairs = {
        (c["a"], c["a_origin"], c["b"], c["b_origin"]) for c in result["conflicts"]
    }
    assert ("L1", "skill", "I1", "skill") in pairs
    assert ("L1", "global", "I1", "global") in pairs
    assert len(result["conflicts"]) == 2  # the two pairs are distinguishable, not deduped away


# --------------------------------------------------------------------------- capture


def test_capture_commits_a_new_learning(env):
    result = capture(
        "gt",
        "learning",
        "Right-align currency columns and drop vertical gridlines.",
        "currency columns",
        "2026-07-16 — 'make revenue right-aligned'",
    )
    result.pop("confirmation", None)
    assert result == {"status": "committed", "entry_id": "L1", "recurrence": 1}

    slug = store_location("gt").slug
    md = list((env / slug / "learnings").glob("*.md"))
    assert md, "a learnings markdown file was written"
    # The store advanced past its initial commit (markdown committed to git).
    assert _commit_count(env, slug) == 2
    # The derived index is not tracked by git.
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=str(env / slug), check=True, capture_output=True, text=True
    ).stdout
    assert "index.sqlite" not in tracked


def test_capture_reinforces_a_near_duplicate_learning(env, monkeypatch):
    # The default dedup cutoff (0.9) is calibrated for sentence-transformers; the lite hashing
    # backend scores paraphrases lower, so exercise dedup at a hashing-appropriate threshold.
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")
    body = "Right-align currency columns and drop vertical gridlines for a clean look."
    first = capture("gt", "learning", body, "currency columns", "prov-1")
    assert first["status"] == "committed"

    again = capture(
        "gt",
        "learning",
        "Please right-align the currency columns and drop vertical gridlines for a clean look.",
        "currency columns",
        "prov-2",
    )
    assert again["status"] == "reinforced"
    assert again["entry_id"] == "L1"
    assert again["recurrence"] == 2

    # Still one learning, now recalled with the bumped weight.
    result = recall("gt", "currency column alignment and gridlines")
    ids = [x["id"] for x in result["learnings"]]
    assert ids == ["L1"]


def test_capture_noops_a_duplicate_issue(env, monkeypatch):
    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")
    body = "Never apply heavy row banding to tables under ten rows."
    first = capture("gt", "issue", body, "small tables", "prov-1")
    first.pop("confirmation", None)
    assert first == {"status": "committed", "entry_id": "I1", "recurrence": None}

    dup = capture(
        "gt",
        "issue",
        "Never use heavy row banding on tables that have under ten rows.",
        "small tables",
        "prov-2",
    )
    dup.pop("confirmation", None)
    assert dup == {"status": "noop", "entry_id": "I1"}


def test_learning_and_issue_ids_are_independent_sequences(env):
    assert capture("gt", "learning", "Prefer muted palettes.", "color", "p")["entry_id"] == "L1"
    assert capture("gt", "issue", "Never use neon.", "color", "p")["entry_id"] == "I1"
    assert capture("gt", "learning", "Prefer serif headers.", "type", "p")["entry_id"] == "L2"
    assert capture("gt", "issue", "Never use comic sans.", "type", "p")["entry_id"] == "I2"


def test_capture_rejects_unknown_polarity(env):
    with pytest.raises(ValueError, match="polarity"):
        capture("gt", "bogus", "body", "scope", "prov")


def test_capture_rejects_empty_body(env):
    with pytest.raises(ValueError, match="non-empty body"):
        capture("gt", "learning", "   ", "scope", "prov")


def test_capture_rejects_delimiter_like_body_and_leaves_store_clean(env):
    from whetstone.embeddings import HashingBackend
    from whetstone.store import index

    capture("gt", "learning", "A real, harmless preference about tables.", "tables", "prov")
    slug = store_location("gt").slug
    commits_before = _commit_count(env, slug)

    # A body containing an entry-heading delimiter line would corrupt the store on the next parse.
    from whetstone.store.markdown import MarkdownParseError

    with pytest.raises(MarkdownParseError, match="entry-heading delimiter"):
        capture(
            "gt",
            "learning",
            "Prefer muted palettes.\n\n## L99 · Example\n\nsneaky.",
            "color palette",
            "prov",
        )

    # No new entry, no new commit, working tree clean, and the index still loads.
    loc = store_location("gt")
    assert {e.id for e in index.load_entries(loc, "learning")} == {"L1"}
    assert _commit_count(env, slug) == commits_before
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(env / slug),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status == ""  # store not left dirty
    index.rebuild_index_if_stale(loc, HashingBackend(dim=384))  # still loads / rebuilds cleanly


def test_recall_honors_configured_learnings_k(env, monkeypatch):
    monkeypatch.setenv("WHETSTONE_LEARNINGS_K", "3")
    # Six DISTINCT styling preferences (in one scope) so none dedups into another.
    bodies = [
        "Use a muted blue color palette for the table.",
        "Right-align every numeric currency column.",
        "Add subtle horizontal row banding.",
        "Increase the cell padding for a roomier layout.",
        "Bold the header row and underline it.",
        "Use a serif typeface for the table caption.",
    ]
    for body in bodies:
        capture("gt", "learning", body, "styling", "prov")
    # No explicit learnings_k -> the configured default (3) applies, not the old hard-coded 12.
    result = recall("gt", "styling a table well")
    assert len(result["learnings"]) == 3


def test_capture_normalizes_scope_for_consistent_files(env, monkeypatch):
    # A messy scope (stray whitespace/newlines) must store + file under the SAME canonical form as
    # its clean version, so a follow-up capture dedups against it instead of forking a new file.
    from whetstone.server import capture
    from whetstone.store.access import load_learnings
    from whetstone.store.layout import store_location

    monkeypatch.setenv("WHETSTONE_DEDUP_SIMILARITY", "0.6")
    r1 = capture("gt", "learning", "Right-align currency columns.", "  currency \n columns ", "p")
    r2 = capture(
        "gt", "learning", "Right-align the currency columns please.", "currency columns", "p"
    )
    assert r1["status"] == "committed"
    assert r2["status"] == "reinforced"  # matched the same normalized scope + near-dup body
    learnings = load_learnings(store_location("gt"))
    assert all(le.scope == "currency columns" for le in learnings)  # stored normalized
    # Exactly one learnings file (no fork from the messy scope).
    assert len(list(store_location("gt").learnings_dir.glob("*.md"))) == 1


def test_run_id_has_high_entropy(env):
    from whetstone.server import recall

    run_id = recall("gt", "styling a table")["run_id"]
    suffix = run_id.rsplit("-", 1)[-1]
    assert len(suffix) == 16  # 64-bit token_hex(8), not the old 4-char/16-bit suffix
