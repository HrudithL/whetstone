"""Whetstone configuration: a dataclass of tunables plus a TOML + env loader.

Precedence (lowest to highest): dataclass defaults < ``config.toml`` < ``WHETSTONE_*`` env vars.

Only ``store_root`` and ``supervision`` are exercised in milestone M0; the remaining keys are
declared with their documented defaults so the config surface is stable for later milestones.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from .paths import config_path, default_store_root

_SUPERVISION_MODES = ("supervised", "balanced", "autonomous")


@dataclass
class Config:
    """Runtime configuration for the Whetstone server."""

    supervision: str = "balanced"
    learnings_half_life_days: int = 180
    learnings_decay: bool = True
    learnings_k: int = 12
    mmr_lambda: float = 0.7
    embedding_model: str = "all-MiniLM-L6-v2"
    store_root: Path = field(default_factory=default_store_root)

    def __post_init__(self) -> None:
        if self.supervision not in _SUPERVISION_MODES:
            raise ValueError(
                f"supervision must be one of {_SUPERVISION_MODES}, got {self.supervision!r}"
            )
        self.store_root = Path(self.store_root).expanduser()


def _coerce(name: str, raw: object) -> object:
    """Coerce a raw string/TOML value to the type of the ``Config`` field ``name``."""
    field_type = _FIELD_TYPES[name]
    if field_type is bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if field_type is int:
        return int(raw)
    if field_type is float:
        return float(raw)
    if field_type is Path:
        return Path(str(raw)).expanduser()
    return str(raw)


_FIELD_TYPES: dict[str, type] = {
    "supervision": str,
    "learnings_half_life_days": int,
    "learnings_decay": bool,
    "learnings_k": int,
    "mmr_lambda": float,
    "embedding_model": str,
    "store_root": Path,
}


def load_config(path: Path | None = None) -> Config:
    """Load configuration from TOML (if present) with ``WHETSTONE_*`` env overrides.

    ``path`` defaults to :func:`whetstone.paths.config_path`. A missing file is fine — the
    dataclass defaults apply.
    """
    values: dict[str, object] = {}

    toml_path = path if path is not None else config_path()
    if toml_path.exists():
        with toml_path.open("rb") as fh:
            data = tomllib.load(fh)
        for name in _FIELD_TYPES:
            if name in data:
                values[name] = _coerce(name, data[name])

    for f in fields(Config):
        env_key = f"WHETSTONE_{f.name.upper()}"
        if env_key in os.environ:
            values[f.name] = _coerce(f.name, os.environ[env_key])

    return Config(**values)
