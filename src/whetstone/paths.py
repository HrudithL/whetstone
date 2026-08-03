"""Per-OS base-directory helpers.

POSIX (macOS/Linux) follows the XDG Base Directory Specification, overridable by the standard
``XDG_*`` environment variables. Windows has no XDG convention, so it uses the native
``%LOCALAPPDATA%``/``%APPDATA%`` locations instead — ``WHETSTONE_STORE_ROOT`` and the config path
env override (handled generically in :mod:`whetstone.config`) work identically on every platform
regardless of which of these a given OS resolves to.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def xdg_data_home() -> Path:
    """The per-OS data home: ``$XDG_DATA_HOME``/``~/.local/share`` (POSIX) or ``%LOCALAPPDATA%``
    (Windows)."""
    if sys.platform == "win32":
        value = os.environ.get("LOCALAPPDATA")
        return Path(value) if value else Path.home() / "AppData" / "Local"
    value = os.environ.get("XDG_DATA_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".local" / "share"


def xdg_config_home() -> Path:
    """The per-OS config home: ``$XDG_CONFIG_HOME``/``~/.config`` (POSIX) or ``%APPDATA%``
    (Windows)."""
    if sys.platform == "win32":
        value = os.environ.get("APPDATA")
        return Path(value) if value else Path.home() / "AppData" / "Roaming"
    value = os.environ.get("XDG_CONFIG_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".config"


def _legacy_windows_home(*parts: str) -> Path:
    """The path Windows would have resolved to before native dirs existed.

    Before this platform split, ``xdg_data_home``/``xdg_config_home`` ran the same POSIX-style
    ``~/.local/share``/``~/.config`` logic unconditionally on every OS (no ``sys.platform`` branch
    existed at all) — so a store created on Windows pre-migration lives at
    ``~/.local/share/whetstone``, not ``%LOCALAPPDATA%\\whetstone``.
    """
    return Path.home().joinpath(*parts)


def default_store_root() -> Path:
    """The default per-skill store root: ``<data-home>/whetstone``.

    On Windows, if a store already exists at the pre-migration legacy location
    (``~/.local/share/whetstone``) but not yet at the native one, the legacy location wins — an
    existing user's learned preferences must not silently appear to vanish after an upgrade.
    """
    native = xdg_data_home() / "whetstone"
    if sys.platform == "win32" and not native.exists():
        legacy = _legacy_windows_home(".local", "share", "whetstone")
        if legacy.exists():
            return legacy
    return native


def config_path() -> Path:
    """The config file path: ``<config-home>/whetstone/config.toml``.

    Same legacy-location fallback as :func:`default_store_root`, for the same reason: an existing
    Windows config file must keep loading after the native-path migration.
    """
    native = xdg_config_home() / "whetstone" / "config.toml"
    if sys.platform == "win32" and not native.exists():
        legacy = _legacy_windows_home(".config", "whetstone", "config.toml")
        if legacy.exists():
            return legacy
    return native
