"""Tests for config defaults, TOML loading, and env overrides."""

from __future__ import annotations

import pytest

from whetstone.config import Config, load_config


def test_defaults():
    cfg = Config()
    assert cfg.supervision == "balanced"
    assert cfg.learnings_half_life_days == 180
    assert cfg.learnings_decay is True
    assert cfg.learnings_k == 12
    assert cfg.mmr_lambda == 0.7
    assert cfg.embedding_model == "all-MiniLM-L6-v2"
    assert cfg.store_root.name == "whetstone"


def test_invalid_supervision_rejected():
    with pytest.raises(ValueError, match="supervision"):
        Config(supervision="bogus")


def test_toml_and_env_precedence(tmp_path, monkeypatch):
    toml = tmp_path / "config.toml"
    toml.write_text(
        'supervision = "supervised"\nlearnings_k = 5\nlearnings_decay = false\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("WHETSTONE_STORE_ROOT", raising=False)
    cfg = load_config(toml)
    assert cfg.supervision == "supervised"
    assert cfg.learnings_k == 5
    assert cfg.learnings_decay is False

    # Env overrides the TOML value.
    monkeypatch.setenv("WHETSTONE_LEARNINGS_K", "20")
    monkeypatch.setenv("WHETSTONE_STORE_ROOT", str(tmp_path / "store"))
    cfg2 = load_config(toml)
    assert cfg2.learnings_k == 20
    assert cfg2.store_root == tmp_path / "store"


def test_missing_toml_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("WHETSTONE_STORE_ROOT", raising=False)
    cfg = load_config(tmp_path / "does-not-exist.toml")
    assert cfg.supervision == "balanced"
