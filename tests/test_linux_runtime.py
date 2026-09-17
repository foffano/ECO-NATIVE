from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.app.core.atomic_files import atomic_write_text
from backend.app.core.playwright_env import find_chromium_executable
from backend.app.core.server_lock import server_lock
from backend.app.services.browser_capacity import browser_lease


def test_linux_x64_chromium_layout(tmp_path):
    binary = tmp_path / "chromium-1200/chrome-linux64/chrome"
    binary.parent.mkdir(parents=True)
    binary.touch()
    assert find_chromium_executable(tmp_path) == binary


def test_failed_atomic_replace_keeps_original(tmp_path, monkeypatch):
    path = tmp_path / "studio.json"
    path.write_text('{"old": true}')
    def fail(*args):
        raise OSError("simulated disk error")
    monkeypatch.setattr("backend.app.core.atomic_files.os.replace", fail)
    with pytest.raises(OSError):
        atomic_write_text(path, '{"new": true}')
    assert path.read_text() == '{"old": true}'
    assert list(tmp_path.iterdir()) == [path]


def test_profile_exclusivity_and_capacity(monkeypatch):
    monkeypatch.setenv("ECO_NATIVE_MAX_BROWSERS", "1")
    with browser_lease("shop-a"):
        with pytest.raises(RuntimeError, match="desta loja"):
            with browser_lease("shop-a"):
                pass
        with pytest.raises(RuntimeError, match="Limite"):
            with browser_lease("shop-b"):
                pass
    with browser_lease("shop-b"):
        pass


def test_context_is_headed_and_releases_profile_after_error(tmp_path, monkeypatch):
    from backend.app.services import makerworld_scraper as scraper
    monkeypatch.setattr(scraper, "configure_playwright_browsers", lambda pw: tmp_path / "chrome")
    monkeypatch.setattr(scraper, "makerworld_profile_dir", lambda shop: tmp_path / shop)
    chromium = MagicMock()
    context = chromium.launch_persistent_context.return_value
    with pytest.raises(ValueError):
        with scraper.open_makerworld_context(SimpleNamespace(chromium=chromium), headless=True, store_profile_id="shop"):
            raise ValueError("navigation failure")
    assert chromium.launch_persistent_context.call_args.kwargs["headless"] is False
    context.close.assert_called_once()
    with browser_lease(str(tmp_path / "shop")):
        pass


def test_single_server_guard():
    import os
    if os.name != "posix":
        pytest.skip("POSIX lock")
    with server_lock():
        with pytest.raises(RuntimeError, match="uma instância"):
            with server_lock():
                pass


def test_corrupt_auth_does_not_reopen_admin_setup():
    from backend.app.services.auth import AUTH_PATH, setup_required
    AUTH_PATH.write_text("{broken")
    with pytest.raises(RuntimeError, match="cadastro inicial permanece bloqueado"):
        setup_required()
