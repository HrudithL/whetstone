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


def _legacy_windows_data_home() -> Path:
    """What ``xdg_data_home`` would have resolved to on Windows before the native-path split.

    Before that split, ``xdg_data_home`` ran the same POSIX-style logic unconditionally on every
    OS (no ``sys.platform`` branch existed at all) — including honoring ``$XDG_DATA_HOME`` if a
    user had set it. A legacy-location check that only probes the hardcoded ``~/.local/share``
    default would miss exactly that user (Codex review finding on PR #55 round 4): replicate the
    full old algorithm, env override included, not just its fallback branch.
    """
    value = os.environ.get("XDG_DATA_HOME")
    return Path(value).expanduser() if value else Path.home() / ".local" / "share"


def _legacy_windows_config_home() -> Path:
    """The config-home equivalent of :func:`_legacy_windows_data_home`."""
    value = os.environ.get("XDG_CONFIG_HOME")
    return Path(value).expanduser() if value else Path.home() / ".config"


def default_store_root() -> Path:
    """The default per-skill store root: ``<data-home>/whetstone``.

    On Windows, if a store already exists at the pre-migration legacy location — honoring
    ``$XDG_DATA_HOME`` if it was set, else ``~/.local/share`` — but not yet at the native one, the
    legacy location wins — an existing user's learned preferences must not silently appear to
    vanish after an upgrade.
    """
    native = xdg_data_home() / "whetstone"
    if sys.platform == "win32" and not native.exists():
        legacy = _legacy_windows_data_home() / "whetstone"
        if legacy.exists():
            return legacy
    return native


def config_path() -> Path:
    """The config file path: ``<config-home>/whetstone/config.toml``.

    Same legacy-location fallback as :func:`default_store_root`, for the same reason: an existing
    Windows config file (and any ``$XDG_CONFIG_HOME``-relative ``store_root`` it defines) must
    keep loading after the native-path migration.
    """
    native = xdg_config_home() / "whetstone" / "config.toml"
    if sys.platform == "win32" and not native.exists():
        legacy = _legacy_windows_config_home() / "whetstone" / "config.toml"
        if legacy.exists():
            return legacy
    return native
