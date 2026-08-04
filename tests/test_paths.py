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


def test_windows_store_root_prefers_existing_legacy_location(monkeypatch, tmp_path):
    """An existing pre-migration Windows store (created before the native-path split existed)
    must keep loading — the native %LOCALAPPDATA% default only applies to a fresh install.

    Patches ``Path.home`` directly rather than the ``HOME`` env var: on real Windows,
    ``pathlib``'s ``expanduser``/``home`` resolution checks ``USERPROFILE`` (always set on a
    Windows runner) before ``HOME``, so setting ``HOME`` alone has no effect there — this must be
    verified on a Windows CI leg, not just locally, for exactly that reason.
    """
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    # Isolate from a real XDG_DATA_HOME the test process's own environment might set (observed on
    # a Linux CI runner: without this, the legacy check consults THAT real path instead of the
    # isolated tmp_path fixture, doesn't find a "whetstone" dir there, and wrongly falls through
    # to the native branch this test isn't testing).
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    legacy = tmp_path / ".local" / "share" / "whetstone"
    legacy.mkdir(parents=True)
    assert paths.default_store_root() == legacy


def test_windows_store_root_prefers_a_legacy_xdg_data_home_override(monkeypatch, tmp_path):
    """A pre-migration Windows user who had explicitly set $XDG_DATA_HOME (not just relied on the
    ~/.local/share default) must also keep loading their store — the legacy check has to replicate
    the OLD algorithm's env-var precedence, not just its fallback branch (Codex round-4 finding)."""
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    custom_xdg = tmp_path / "custom-xdg-data"
    monkeypatch.setenv("XDG_DATA_HOME", str(custom_xdg))
    legacy = custom_xdg / "whetstone"
    legacy.mkdir(parents=True)
    # A ~/.local/share/whetstone dir must NOT be what's returned even if it happens to exist too —
    # the env override takes precedence, exactly as it did before the native-path split.
    (tmp_path / ".local" / "share" / "whetstone").mkdir(parents=True)
    assert paths.default_store_root() == legacy


def test_windows_store_root_uses_native_location_for_a_fresh_install(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)  # isolate from the real environment
    # No legacy directory exists — a brand new install goes straight to the native path.
    assert paths.default_store_root() == tmp_path / "AppData" / "Local" / "whetstone"


def test_windows_config_path_prefers_existing_legacy_location(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("APPDATA", raising=False)
    # Isolate from a real XDG_CONFIG_HOME the test process's own environment might set — this is
    # exactly what broke on CI: without it, the legacy check consulted that real path instead of
    # tmp_path, found no "whetstone" dir there, and wrongly fell through to the native branch.
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    legacy = tmp_path / ".config" / "whetstone"
    legacy.mkdir(parents=True)
    (legacy / "config.toml").write_text("supervision = 'autonomous'\n")
    assert paths.config_path() == legacy / "config.toml"
