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


def default_store_root() -> Path:
    """The default per-skill store root: ``<xdg-data-home>/whetstone``."""
    return xdg_data_home() / "whetstone"


def config_path() -> Path:
    """The config file path: ``<xdg-config-home>/whetstone/config.toml``."""
    return xdg_config_home() / "whetstone" / "config.toml"
