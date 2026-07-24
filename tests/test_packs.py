"""M5c — preference packs: round-trip export/import, dedup merge, conflict surfacing, --replace."""

from __future__ import annotations

import tarfile
from datetime import date

import pytest

from whetstone.packs import export_pack, import_pack, read_manifest
from whetstone.server import capture
from whetstone.store.access import load_issues, load_learnings
from whetstone.store.layout import store_location

TODAY = date(2026, 7, 24)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path))
    monkeypatch.setenv("WHETSTONE_CONSULT_GLOBAL", "false")
    return tmp_path


def _seed_source():
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    capture("gt", "learning", "Use subtle zebra striping on wide tables.", "row banding", "prov")
    capture("gt", "issue", "Never band tables under ten rows.", "small tables", "prov")


# --------------------------------------------------------------------------- export


def test_export_writes_pack_with_manifest_and_markdown(env):
    _seed_source()
    out = env / "gt-pack.tar.gz"
    summary = export_pack("gt", out)

    assert summary["learnings"] == 2
    assert summary["issues"] == 1
    assert out.exists()
    with tarfile.open(out) as tar:
        names = tar.getnames()
    assert "pack.toml" in names
    assert any(n.startswith("learnings/") and n.endswith(".md") for n in names)
    assert any(n.startswith("issues/") and n.endswith(".md") for n in names)
    # Telemetry / derived artifacts are excluded.
    assert not any("events.jsonl" in n or "index.sqlite" in n or ".git" in n for n in names)


def test_export_manifest_fields(env):
    _seed_source()
    out = env / "gt-pack.tar.gz"
    export_pack("gt", out)
    manifest = read_manifest(out)
    assert manifest["skill"] == "gt"
    assert manifest["learnings"] == 2
    assert manifest["issues"] == 1
    assert "currency" in manifest["scopes"]
    assert manifest["whetstone_version"]


# --------------------------------------------------------------------------- import round-trip


def test_import_into_fresh_store_remints_ids(env):
    _seed_source()
    out = env / "gt-pack.tar.gz"
    export_pack("gt", out)

    result = import_pack("fresh", out, today=TODAY)
    assert result["committed"] == 3
    assert result["conflicts"] == 0
    learnings = load_learnings(store_location("fresh"))
    issues = load_issues(store_location("fresh"))
    assert len(learnings) == 2
    assert len(issues) == 1
    # Ids are freshly minted in the target, not carried over.
    assert {e.id for e in learnings} == {"L1", "L2"}
    bodies = {e.body for e in learnings}
    assert any("currency" in b for b in bodies)


def test_import_preserves_recurrence_resets_last_seen(env):
    # Seed a source learning with recurrence 3 by reinforcing.
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")  # dedup -> rec 2
    out = env / "gt-pack.tar.gz"
    export_pack("gt", out)

    import_pack("fresh", out, today=TODAY)
    learning = load_learnings(store_location("fresh"))[0]
    assert learning.recurrence == 2  # honored from the pack
    assert learning.last_seen == TODAY  # reset for a fair decay start


# --------------------------------------------------------------------------- merge dedup + conflict


def test_merge_folds_exact_duplicate(env):
    capture("gt", "learning", "Right-align currency columns.", "currency", "prov")
    out = env / "gt-pack.tar.gz"
    export_pack("gt", out)

    # Import the SAME pack back into gt: the identical learning dedups (folds), not doubles.
    result = import_pack("gt", out, today=TODAY)
    assert result["merged"] == 1
    assert result["committed"] == 0
    learnings = load_learnings(store_location("gt"))
    assert len(learnings) == 1
    assert learnings[0].recurrence == 2  # 1 (existing) + 1 (incoming)


def test_merge_surfaces_conflict_not_applied(env, monkeypatch):
    # Force the conflict detector to fire deterministically (hashing won't cross the ST cutoff).
    import whetstone.packs as packs

    monkeypatch.setattr(
        packs, "_find_conflict", lambda *a, **k: (_FakeEntry("I9"), "planted conflict")
    )
    capture("gt", "learning", "Prefer neon palettes.", "palette", "prov")
    out = env / "gt-pack.tar.gz"
    export_pack("gt", out)

    result = import_pack("target", out, today=TODAY)
    assert result["conflicts"] == 1
    assert result["committed"] == 0
    # The conflicting entry was surfaced, never written.
    assert load_learnings(store_location("target")) == []


class _FakeEntry:
    def __init__(self, id):
        self.id = id


# --------------------------------------------------------------------------- replace


def test_replace_wipes_then_imports(env):
    _seed_source()
    out = env / "gt-pack.tar.gz"
    export_pack("gt", out)

    # Target already has an unrelated learning that --replace must clear.
    capture("target", "learning", "Some old unrelated preference.", "misc", "prov")
    result = import_pack("target", out, "replace", today=TODAY)

    assert result["mode"] == "replace"
    learnings = load_learnings(store_location("target"))
    issues = load_issues(store_location("target"))
    assert len(learnings) == 2  # only the pack's learnings; the old one is gone
    assert len(issues) == 1
    assert all("unrelated" not in e.body for e in learnings)


def test_import_missing_pack_raises(env):
    with pytest.raises(FileNotFoundError):
        import_pack("gt", env / "nope.tar.gz")


def test_import_bad_mode_raises(env):
    _seed_source()
    out = env / "gt-pack.tar.gz"
    export_pack("gt", out)
    with pytest.raises(ValueError, match="mode must be"):
        import_pack("gt", out, "sideways")
