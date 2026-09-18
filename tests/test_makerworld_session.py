import time
from types import SimpleNamespace
from unittest.mock import MagicMock, call
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from backend.app.db.models import StoreProfile
from backend.app.db.store import store
from backend.app.services import makerworld_session as session_module
from backend.app.services.makerworld_scraper import MAKERWORLD_HOME
from backend.app.services.makerworld_session import (
    CHALLENGE_MESSAGE,
    LOADING_MAX_SECONDS,
    MAKERWORLD_LOGIN_URL,
    NAVIGATION_TIMEOUT_MS,
    BrowserPages,
    RemoteBrowserSession,
)


class FakeTarget:
    def __init__(self):
        self.handlers = {}
        self.pages = []
        self.main_frame = object()
        self.url = "https://makerworld.com/pt"

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event, argument=None):
        for handler in self.handlers.get(event, []):
            handler(argument)

    def is_closed(self):
        return False


def request(frame, navigation=True):
    return SimpleNamespace(frame=frame, is_navigation_request=lambda: navigation)


def test_login_url_returns_through_makerworld_ticket():
    url = urlparse(MAKERWORLD_LOGIN_URL)
    assert (url.scheme, url.netloc, url.path) == ("https", "bambulab.com", "/pt-br/sign-in")
    query = parse_qs(url.query)
    assert query["ticket"] == ["1"]
    back = urlparse(query["to"][0])
    assert (back.netloc, back.path) == ("makerworld.com", "/api/sign-in/ticket")
    assert parse_qs(back.query)["to"] == ["https://makerworld.com/pt"]


def test_navigate_only_reaches_fixed_destinations():
    session = RemoteBrowserSession("shop")
    page = MagicMock()
    session._execute(page, {"type": "navigate", "action": "login"})
    session._execute(page, {"type": "navigate", "action": "home"})
    session._execute(page, {"type": "navigate", "action": "back"})
    session._execute(page, {"type": "navigate", "action": "reload"})
    session._execute(page, {"type": "navigate", "action": "https://example.com"})
    assert page.goto.call_args_list == [
        call(MAKERWORLD_LOGIN_URL, wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS),
        call(MAKERWORLD_HOME, wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS),
    ]
    page.go_back.assert_called_once_with(wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS)
    page.reload.assert_called_once_with(wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS)


def test_loading_follows_main_frame_navigation(monkeypatch):
    context, page = FakeTarget(), FakeTarget()
    context.pages = [page]
    changes = []
    windows = BrowserPages(context, on_loading_change=lambda pages: changes.append(pages.is_loading("1")))

    page.emit("request", request(object()))
    page.emit("request", request(page.main_frame, navigation=False))
    assert not windows.is_loading("1")

    navigation = request(page.main_frame)
    page.emit("request", navigation)
    page.emit("requestfailed", request(page.main_frame))
    assert windows.is_loading("1")
    page.emit("domcontentloaded")
    assert not windows.is_loading("1")

    # A navigation that turns into a download fails instead of loading a document.
    page.emit("request", navigation)
    page.emit("requestfailed", navigation)
    assert not windows.is_loading("1")

    page.emit("request", navigation)
    later = time.monotonic() + LOADING_MAX_SECONDS + 1
    monkeypatch.setattr(session_module.time, "monotonic", lambda: later)
    assert not windows.is_loading("1")
    assert changes == [True, False, True, False, True]


def test_status_explains_cloudflare_challenge(monkeypatch):
    session = RemoteBrowserSession("shop")
    session._challenge = True
    assert not session.status().challenge

    monkeypatch.setattr(session._thread, "is_alive", lambda: True)
    session._open = True
    status = session.status()
    assert status.challenge
    assert status.message == CHALLENGE_MESSAGE
    session._error = "timeout"
    assert session.status().message == "Falha no navegador MakerWorld: timeout"


def test_remote_input_accepts_only_known_navigation(monkeypatch):
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session

    shop = store.upsert_store_profile(StoreProfile(name="A"))
    create_initial_users(("admin", "password123"), [("shop-a", "password123", shop.id)])
    sent = []
    monkeypatch.setattr(
        "backend.app.api.routes_jobs.send_login_session_input",
        lambda store_id, command: sent.append((store_id, command)),
    )
    with TestClient(app) as client:
        client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "shop-a")))
        url = "/api/jobs/makerworld-login/input"
        assert client.post(url, json={"type": "navigate", "action": "login", "page_id": "1"}).status_code == 204
        assert client.post(url, json={"type": "navigate", "action": "https://example.com"}).status_code == 422
    assert sent == [(shop.id, {"type": "navigate", "page_id": "1", "action": "login", "button": "left"})]


def test_drag_replays_the_pointer_path_within_the_viewport():
    session = RemoteBrowserSession("shop")
    page = MagicMock()
    session._execute(page, {"type": "down", "x": 10, "y": 20, "button": "left"})
    session._execute(page, {"type": "move", "path": [(15, 20, 0), (5000, 30, 900)]})
    session._execute(page, {"type": "up", "x": 40, "y": 20, "button": "left"})
    assert page.mouse.method_calls == [
        call.move(10.0, 20.0),
        call.down(button="left"),
        call.move(15.0, 20.0),
        call.move(1280.0, 30.0),
        call.move(40.0, 20.0),
        call.up(button="left"),
    ]
    page.wait_for_timeout.assert_called_once_with(200)


def test_panel_follows_a_running_collect_browser(monkeypatch):
    started = []

    class FakeViewer:
        def __init__(self, store_profile_id, attach_endpoint=None):
            self.attached = attach_endpoint is not None
            self.endpoint = attach_endpoint
            self.closed = False
            self._thread = SimpleNamespace(is_alive=lambda: not self.closed)
            started.append(self)

        def start(self):
            pass

        def close(self):
            self.closed = True

        def frame(self):
            return b"jpeg"

    monkeypatch.setattr(session_module, "RemoteBrowserSession", FakeViewer)
    assert session_module.get_login_session_status("shop").mode == "login"
    with session_module.watch_collect_browser("shop", "http://127.0.0.1:9222"):
        status = session_module.get_login_session_status("shop")
        assert (status.mode, status.open) == ("collect", False)
        assert not started  # Polling status alone does not start a viewer.
        session_module.set_collect_notice("shop", "Resolva a verificação")
        status = session_module.get_login_session_status("shop")
        assert (status.message, status.attention) == ("Resolva a verificação", True)
        assert session_module.get_login_session_frame("shop") == b"jpeg"
        assert [viewer.endpoint for viewer in started] == ["http://127.0.0.1:9222"]
    assert started[0].closed
    assert session_module.get_login_session_status("shop").mode == "login"
    assert "shop" not in session_module._collect_notices


def test_remote_input_validates_drag_paths(monkeypatch):
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session

    shop = store.upsert_store_profile(StoreProfile(name="A"))
    create_initial_users(("admin", "password123"), [("shop-a", "password123", shop.id)])
    monkeypatch.setattr("backend.app.api.routes_jobs.send_login_session_input", lambda store_id, command: None)
    with TestClient(app) as client:
        client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "shop-a")))
        url = "/api/jobs/makerworld-login/input"
        assert client.post(url, json={"type": "down", "x": 10, "y": 10}).status_code == 204
        assert client.post(url, json={"type": "move", "path": [[10, 10, 16], [20, 12, 16]]}).status_code == 204
        assert client.post(url, json={"type": "move", "path": [[10, 900, 16]]}).status_code == 422
        assert client.post(url, json={"type": "move", "path": [[1, 1, 1]] * 121}).status_code == 422
