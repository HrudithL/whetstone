"""Per-OS base-directory resolution (whetstone.paths)."""

from pathlib import Path

from whetstone import paths


def test_xdg_data_home_env_override(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg-data")
    assert paths.xdg_data_home() == Path("/tmp/xdg-data")


def test_xdg_data_home_default(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert paths.xdg_data_home() == Path.home() / ".local" / "share"


def test_xdg_config_home_env_override(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg-config")
    assert paths.xdg_config_home() == Path("/tmp/xdg-config")


def test_xdg_config_home_default(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert paths.xdg_config_home() == Path.home() / ".config"


def test_windows_data_home_uses_localappdata(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
    assert paths.xdg_data_home() == Path(r"C:\Users\test\AppData\Local")


def test_windows_data_home_falls_back_without_localappdata(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert paths.xdg_data_home() == Path.home() / "AppData" / "Local"


def test_windows_config_home_uses_appdata(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    assert paths.xdg_config_home() == Path(r"C:\Users\test\AppData\Roaming")


def test_windows_config_home_falls_back_without_appdata(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    assert paths.xdg_config_home() == Path.home() / "AppData" / "Roaming"


def test_windows_ignores_xdg_env_vars(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("XDG_DATA_HOME", "/should/be/ignored")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
    assert paths.xdg_data_home() == Path(r"C:\Users\test\AppData\Local")


def test_default_store_root_and_config_path(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg-data")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg-config")
    assert paths.default_store_root() == Path("/tmp/xdg-data/whetstone")
    assert paths.config_path() == Path("/tmp/xdg-config/whetstone/config.toml")
