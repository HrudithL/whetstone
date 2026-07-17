"""XDG base-directory helpers.

See the XDG Base Directory Specification. Whetstone stores per-skill data under the XDG data
dir and reads its config from the XDG config dir; both are overridable by the standard
``XDG_*`` environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path


def xdg_data_home() -> Path:
    """The XDG data home (``$XDG_DATA_HOME`` or ``~/.local/share``)."""
    value = os.environ.get("XDG_DATA_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".local" / "share"


def xdg_config_home() -> Path:
    """The XDG config home (``$XDG_CONFIG_HOME`` or ``~/.config``)."""
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
