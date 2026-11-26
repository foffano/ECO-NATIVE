from contextlib import ExitStack, contextmanager
import queue
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright, Error as PlaywrightError
from websockets.exceptions import ConnectionClosed

from backend.app.services.cdp_viewer import CdpError, CdpPage
from backend.app.services.makerworld_scraper import (
    MAKERWORLD_HOME,
    is_cloudflare_challenge,
    makerworld_profile_dir,
    open_makerworld_context,
)


VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
FRAME_INTERVAL_SECONDS = 0.45
# Previews of the collect's other pages: small and refreshed rarely, to spare the server's CPU.
PREVIEW_INTERVAL_SECONDS = 2.0
PREVIEW_RETRY_SECONDS = 10.0
SESSION_IDLE_SECONDS = 30 * 60
# A viewer attached to a collect browser stops capturing once nobody has fetched a frame for this long.
VIEWER_IDLE_SECONDS = 60
NAVIGATION_TIMEOUT_MS = 20_000
# Downloads and 204 responses never reach DOMContentLoaded; stop showing them as loading.
LOADING_MAX_SECONDS = 20
# Same destination as MakerWorld's own login button. After Bambu Lab signs in,
# the ticket redirect creates the MakerWorld session in this profile.
MAKERWORLD_LOGIN_URL = "https://bambulab.com/pt-br/sign-in?" + urlencode({
    "ticket": "1",
    "to": "https://makerworld.com/api/sign-in/ticket?" + urlencode({"to": MAKERWORLD_HOME}),
})
CHALLENGE_MESSAGE = (
    "Verificação de segurança da Cloudflare: marque a caixa “Verify you are human” "
    "e aguarde alguns segundos. Se não avançar, use Recarregar."
)
COLLECT_MESSAGE = (
    "Navegador da coleta: acompanhe e, se o MakerWorld pedir verificação ou puzzle, resolva por aqui."
)


@dataclass
class MakerWorldSessionStatus:
    open: bool
    url: str | None = None
    message: str = ""
    configured: bool = False
    width: int = VIEWPORT_WIDTH
    height: int = VIEWPORT_HEIGHT
    pages: list[dict[str, str]] = field(default_factory=list)
    active_page_id: str | None = None
    loading: bool = False
    challenge: bool = False
    attention: bool = False
    mode: str = "login"
    # Collect browser: the page the collect works on, and whether the view follows it.
    job_page_id: str | None = None
    following: bool = True


class BrowserPages:
    """Track popup lifetime independently of context.pages ordering."""
    def __init__(self, context, on_loading_change=None):
        self.pages = {}
        self.active_id = None
        self._next_id = 0
        self._navigations = {}
        self._on_loading_change = on_loading_change or (lambda windows: None)
        context.on("page", self.add)
        for page in context.pages:
            self.add(page)

    def add(self, page):
        if page in self.pages.values():
            return
        self._next_id += 1
        key = str(self._next_id)
        self.pages[key] = page
        self.active_id = key
        page.on("close", lambda _: self.remove(key))
        # Events arrive during screenshots, so the panel shows the navigation before the new page paints.
        page.on("request", lambda request: self._navigation_started(key, page, request))
        page.on("requestfailed", lambda request: self._navigation_failed(key, request))
        page.on("domcontentloaded", lambda _: self._navigation_finished(key))

    def _navigation_started(self, key, page, request):
        try:
            if not request.is_navigation_request() or request.frame != page.main_frame:
                return
        except PlaywrightError:
            return
        self._navigations[key] = (request, time.monotonic())
        self._on_loading_change(self)

    def _navigation_failed(self, key, request):
        navigation = self._navigations.get(key)
        if navigation and navigation[0] is request:
            self._navigation_finished(key)

    def _navigation_finished(self, key):
        if self._navigations.pop(key, None):
            self._on_loading_change(self)

    def is_loading(self, key):
        navigation = self._navigations.get(key)
        return bool(navigation) and time.monotonic() - navigation[1] < LOADING_MAX_SECONDS

    def remove(self, key):
        self.pages.pop(key, None)
        self._navigations.pop(key, None)
        if self.active_id == key:
            self.active_id = next(reversed(self.pages), None)

    def select(self, key):
        if key in self.pages and not self.pages[key].is_closed():
            self.active_id = key

    def current(self):
        for key, page in list(self.pages.items()):
            if page.is_closed():
                self.remove(key)
        return self.pages.get(self.active_id)

    def describe(self):
        return [{"id": key, "url": page.url} for key, page in self.pages.items() if not page.is_closed()]


class RemoteBrowserSession:
    """Stream one MakerWorld browser to the panel and forward its input.

    Without attach_endpoint it launches the store's login browser. With it, it attaches a passive
    DevTools client to the browser a collect job is driving; the job keeps ownership.
    """
    def __init__(self, store_profile_id: str, attach_endpoint: str | None = None) -> None:
        self.store_profile_id = store_profile_id
        self.attached = attach_endpoint is not None
        self._endpoint = attach_endpoint
        self._last_view = time.monotonic()
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._url: str | None = None
        self._error: str | None = None
        self._open = False
        self._pages = []
        self._active_page_id = None
        self._loading = False
        self._challenge = False
        self._last_activity = time.monotonic()
        # Collect browser only: a page the user picked to see instead of the collect's, and previews.
        self._pinned: str | None = None
        self._job_page_id: str | None = None
        self._previews: dict[str, bytes] = {}
        self._preview_challenges: dict[str, bool] = {}
        self._thread = threading.Thread(target=self._run, name=f"makerworld-{store_profile_id[:8]}", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def status(self) -> MakerWorldSessionStatus:
        with self._lock:
            is_open = self._open and self._thread.is_alive()
            url = self._url
            error = self._error
            pages = list(self._pages)
            active_page_id = self._active_page_id
            loading = is_open and self._loading
            challenge = is_open and self._challenge
            job_page_id = self._job_page_id
            following = self._pinned is None
        configured = _configured(self.store_profile_id)
        notice = _collect_notices.get(self.store_profile_id) if self.attached else None
        if error:
            message = f"Falha no navegador MakerWorld: {error}"
        elif notice:
            message = notice
        elif challenge:
            message = CHALLENGE_MESSAGE
        elif self.attached:
            message = COLLECT_MESSAGE
        elif is_open:
            message = (
                "Navegador MakerWorld oculto no servidor e disponível para controle remoto."
                if os.getenv("ECO_NATIVE_PRIVATE_DESKTOP") == "1" or os.getenv("DISPLAY")
                else "Navegador MakerWorld visível no PC e disponível para controle remoto."
            )
        elif configured:
            message = "Sessão MakerWorld salva para esta loja."
        else:
            message = "Sessão MakerWorld ainda não configurada para esta loja."
        return MakerWorldSessionStatus(open=is_open, url=url, message=message, configured=configured,
                                       pages=pages, active_page_id=active_page_id,
                                       loading=loading, challenge=challenge, attention=bool(notice),
                                       mode="collect" if self.attached else "login",
                                       job_page_id=job_page_id, following=following)

    def frame(self) -> bytes | None:
        self._last_view = time.monotonic()
        with self._lock:
            return self._frame

    def send(self, command: dict[str, Any]) -> None:
        self._last_activity = time.monotonic()
        try:
            self.commands.put_nowait(command)
        except queue.Full:
            try:
                self.commands.get_nowait()
            except queue.Empty:
                pass
            self.commands.put_nowait(command)

    def close(self) -> None:
        self.send({"type": "close"})

    def _execute(self, page, command: dict[str, Any]) -> bool:
        kind = command.get("type")
        if kind == "close":
            return False
        if kind == "click":
            page.mouse.click(*_clamp(command.get("x", 0), command.get("y", 0)), button=command.get("button", "left"))
        elif kind in ("down", "up"):
            # Drags (slider puzzles) arrive as down, move paths and up.
            page.mouse.move(*_clamp(command.get("x", 0), command.get("y", 0)))
            press = page.mouse.down if kind == "down" else page.mouse.up
            press(button=command.get("button", "left"))
        elif kind == "move":
            for x, y, delay_ms in command.get("path") or [(command.get("x", 0), command.get("y", 0), 0)]:
                if delay_ms:
                    page.wait_for_timeout(min(float(delay_ms), 200))
                page.mouse.move(*_clamp(x, y))
        elif kind == "wheel":
            page.mouse.wheel(float(command.get("delta_x", 0)), float(command.get("delta_y", 0)))
        elif kind == "text":
            page.keyboard.insert_text(str(command.get("text", ""))[:2000])
        elif kind == "key":
            key = str(command.get("key", ""))[:80]
            if key:
                page.keyboard.press(key)
        elif kind == "navigate":
            # Fixed destinations only: the panel must not turn the server browser into an open proxy.
            action = command.get("action")
            if action == "login":
                page.goto(MAKERWORLD_LOGIN_URL, wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS)
            elif action == "home":
                page.goto(MAKERWORLD_HOME, wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS)
            elif action == "back":
                page.go_back(wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS)
            elif action == "reload":
                page.reload(wait_until="commit", timeout=NAVIGATION_TIMEOUT_MS)
        return True

    def _track_loading(self, windows: BrowserPages) -> None:
        with self._lock:
            self._loading = windows.is_loading(windows.active_id)

    def _run(self) -> None:
        if self.attached:
            self._run_attached()
            return
        try:
            with sync_playwright() as playwright, ExitStack() as contexts:
                context = contexts.enter_context(open_makerworld_context(
                    playwright,
                    headless=False,
                    store_profile_id=self.store_profile_id,
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                ))
                windows = BrowserPages(context, on_loading_change=self._track_loading)
                page = windows.current() or context.new_page()
                page.goto(os.getenv("ECO_NATIVE_MAKERWORLD_URL", MAKERWORLD_HOME), wait_until="domcontentloaded", timeout=60_000)
                with self._lock:
                    self._open = True
                running = True
                while running and windows.current():
                    if time.monotonic() - self._last_activity > SESSION_IDLE_SECONDS:
                        break
                    while True:
                        try:
                            command = self.commands.get_nowait()
                            if command.get("type") == "select_page":
                                windows.select(command.get("page_id"))
                                continue
                            page = windows.current()
                            if command.get("type") == "close":
                                running = False
                            elif page:
                                # Ignore input from a frame belonging to a different window.
                                target = command.get("page_id")
                                if target is None or target == windows.active_id:
                                    running = self._execute(page, command)
                            if not running:
                                break
                        except queue.Empty:
                            break
                        except PlaywrightError as exc:
                            if not page.is_closed():
                                with self._lock:
                                    self._error = str(exc)
                    if not running:
                        break
                    try:
                        page = windows.current()
                        if page is None:
                            break
                        page_id = windows.active_id
                        if page.viewport_size != {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}:
                            page.set_viewport_size({"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
                        if page_id != self._active_page_id:
                            page.bring_to_front()
                        frame = page.screenshot(type="jpeg", quality=68, animations="disabled", timeout=5_000)
                        challenge = is_cloudflare_challenge(page)
                        with self._lock:
                            if windows.active_id == page_id and not page.is_closed():
                                self._frame = frame
                                self._url = page.url
                                self._active_page_id = page_id
                                self._error = None
                                self._challenge = challenge
                            self._pages = windows.describe()
                            self._loading = windows.is_loading(windows.active_id)
                        # Pump Playwright events while idle so popup/close events arrive.
                        page.wait_for_timeout(FRAME_INTERVAL_SECONDS * 1000)
                    except PlaywrightError as exc:
                        if not page.is_closed():
                            with self._lock:
                                self._error = f"Falha ao atualizar a janela: {exc}"
                context.close()
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
        finally:
            with self._lock:
                self._open = False

    def _run_attached(self) -> None:
        """Stream the collect job's page and pass pointer and keyboard input; the job keeps driving it.

        With several pages open, the others show as small previews refreshed every few seconds.
        The user can pick one to see and control it; the view then stays there until they go
        back to following the collect, or the collect asks for help on another page.
        """
        page = None
        previews_due = 0.0
        retry_at: dict[str, float] = {}
        last_notice = None
        try:
            page = CdpPage(self._endpoint, target_id=_collect_targets.get(self.store_profile_id))
            with self._lock:
                self._open = True
                self._active_page_id = page.target_id
            while time.monotonic() - self._last_view < VIEWER_IDLE_SECONDS:
                while True:
                    try:
                        command = self.commands.get_nowait()
                    except queue.Empty:
                        break
                    if command.get("type") == "close":
                        return
                    if command.get("type") == "select_page":
                        # No page id means follow the collect again.
                        with self._lock:
                            self._pinned = command.get("page_id") or None
                        continue
                    # Navigation stays with the job; only pointer and keyboard input pass through.
                    if command.get("type") == "navigate":
                        continue
                    try:
                        self._execute(page, command)
                    except CdpError as exc:
                        with self._lock:
                            self._error = str(exc)
                job_target = _collect_targets.get(self.store_profile_id)
                notice = _collect_notices.get(self.store_profile_id)
                with self._lock:
                    if notice and notice != last_notice and self._pinned and self._pinned != job_target:
                        self._pinned = None  # The collect needs the user on its own page.
                    wanted = self._pinned or job_target
                last_notice = notice
                if wanted and wanted != page.target_id:
                    try:
                        page.switch_to(wanted)
                    except CdpError:
                        pass  # Try again on the next frame.
                    if page.target_id != wanted:
                        with self._lock:
                            if self._pinned == wanted:
                                self._pinned = None  # That page closed.
                try:
                    frame = page.screenshot()
                    challenge, ready_state = page.evaluate("[Boolean(window._cf_chl_opt), document.readyState]")
                except CdpError:
                    # The tab is between pages; keep showing the last frame.
                    frame, challenge, ready_state = None, False, "loading"
                url = page.url
                pages = [{"id": page.target_id or "1", "url": url}]
                job_tabs = _collect_tabs.get(self.store_profile_id) or []
                if len(job_tabs) > 1:
                    pages = self._describe_tabs(page, job_tabs, previews_due <= time.monotonic(), retry_at)
                    if previews_due <= time.monotonic():
                        previews_due = time.monotonic() + PREVIEW_INTERVAL_SECONDS
                with self._lock:
                    if frame:
                        self._frame = frame
                        self._error = None
                    self._url = url
                    self._pages = pages
                    self._active_page_id = page.target_id
                    self._job_page_id = job_target
                    self._challenge = challenge
                    self._loading = ready_state != "complete"
                time.sleep(FRAME_INTERVAL_SECONDS)
        except Exception as exc:
            # A closed socket just means the collect finished with this browser.
            if not isinstance(exc, ConnectionClosed):
                with self._lock:
                    self._error = str(exc)
        finally:
            if page is not None:
                page.close()
            with self._lock:
                self._open = False

    def _describe_tabs(self, page, job_tabs, refresh: bool, retry_at: dict[str, float]) -> list[dict[str, Any]]:
        """The collect's pages for the panel, refreshing the previews of those not on screen."""
        states = {tab["id"]: tab.get("state", "idle") for tab in job_tabs}
        try:
            urls = {tab["targetId"]: tab["url"] for tab in page.tabs()}
        except CdpError:
            urls = {}
        described = []
        for target_id, state in states.items():
            if target_id not in urls:
                continue
            with self._lock:
                challenge = self._preview_challenges.get(target_id, False)
            now = time.monotonic()
            if refresh and target_id != page.target_id and retry_at.get(target_id, 0) <= now:
                try:
                    preview = page.thumbnail(target_id, VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
                    challenge = bool(page.evaluate_in(target_id, "Boolean(window._cf_chl_opt)"))
                    with self._lock:
                        self._previews[target_id] = preview
                        self._preview_challenges[target_id] = challenge
                except CdpError:
                    # A page Chromium does not paint right now; keep the last preview a while.
                    retry_at[target_id] = now + PREVIEW_RETRY_SECONDS
            with self._lock:
                has_preview = target_id in self._previews
            described.append({
                "id": target_id,
                "url": urls[target_id],
                "state": "verification" if challenge and state != "idle" else state,
                "preview": "1" if has_preview else "",
            })
        return described

    def preview(self, page_id: str) -> bytes | None:
        self._last_view = time.monotonic()
        with self._lock:
            return self._previews.get(page_id)


def _clamp(x, y) -> tuple[float, float]:
    return max(0.0, min(VIEWPORT_WIDTH, float(x))), max(0.0, min(VIEWPORT_HEIGHT, float(y)))


_sessions: dict[str, RemoteBrowserSession] = {}
_sessions_lock = threading.Lock()
# DevTools endpoints of browsers that collect jobs are driving, and what the job needs from the user.
_collect_endpoints: dict[str, str] = {}
_collect_notices: dict[str, str] = {}
# The DevTools target of the tab each collect job is working on, when it uses several tabs.
_collect_targets: dict[str, str] = {}
# What each of those pages is doing: [{"id": target, "state": ...}].
_collect_tabs: dict[str, list[dict[str, str]]] = {}


def _configured(store_profile_id: str) -> bool:
    profile_dir = makerworld_profile_dir(store_profile_id)
    return profile_dir.exists() and any(path.is_file() for path in profile_dir.rglob("*"))


def _session(store_profile_id: str) -> RemoteBrowserSession | None:
    with _sessions_lock:
        session = _sessions.get(store_profile_id)
        if session and not session._thread.is_alive() and not session.status().open:
            _sessions.pop(store_profile_id, None)
            return None
        return session


@contextmanager
def watch_collect_browser(store_profile_id: str, endpoint: str | None):
    """Let the panel watch a collect browser for as long as the job keeps it open."""
    if endpoint:
        with _sessions_lock:
            _collect_endpoints[store_profile_id] = endpoint
    try:
        yield
    finally:
        viewer = None
        with _sessions_lock:
            _collect_endpoints.pop(store_profile_id, None)
            _collect_notices.pop(store_profile_id, None)
            _collect_targets.pop(store_profile_id, None)
            _collect_tabs.pop(store_profile_id, None)
            if getattr(_sessions.get(store_profile_id), "attached", False):
                viewer = _sessions.pop(store_profile_id)
        if viewer is not None:
            viewer.close()


def set_collect_notice(store_profile_id: str, message: str | None) -> None:
    if message:
        _collect_notices[store_profile_id] = message
    else:
        _collect_notices.pop(store_profile_id, None)


def set_collect_target(store_profile_id: str, target_id: str) -> None:
    _collect_targets[store_profile_id] = target_id


def set_collect_tabs(store_profile_id: str, tabs: list[dict[str, str]]) -> None:
    _collect_tabs[store_profile_id] = tabs


def _collect_viewer(store_profile_id: str) -> RemoteBrowserSession | None:
    """Attach to the store's running collect browser; viewers start on demand and stop when unwatched."""
    with _sessions_lock:
        endpoint = _collect_endpoints.get(store_profile_id)
        if not endpoint:
            return None
        session = _sessions.get(store_profile_id)
        if session is None or not session._thread.is_alive():
            session = RemoteBrowserSession(store_profile_id, attach_endpoint=endpoint)
            _sessions[store_profile_id] = session
            session.start()
        return session


def open_login_session(store_profile_id: str) -> MakerWorldSessionStatus:
    # While a collect uses the profile, show that browser instead of launching another one.
    viewer = _collect_viewer(store_profile_id)
    if viewer is not None:
        return viewer.status()
    with _sessions_lock:
        existing = _sessions.get(store_profile_id)
        if existing and existing._thread.is_alive():
            existing.send({"type": "move", "x": 0, "y": 0})
            return existing.status()
        session = RemoteBrowserSession(store_profile_id)
        _sessions[store_profile_id] = session
        session.start()
    return MakerWorldSessionStatus(
        open=True,
        message="Iniciando navegador MakerWorld para controle pelo painel...",
        configured=_configured(store_profile_id),
    )


def close_login_session(store_profile_id: str) -> MakerWorldSessionStatus:
    session = _session(store_profile_id)
    if session:
        session.close()
        session._thread.join(timeout=8)
        with _sessions_lock:
            if _sessions.get(store_profile_id) is session and not session._thread.is_alive():
                _sessions.pop(store_profile_id, None)
    return MakerWorldSessionStatus(
        open=False,
        message="Fechando navegador MakerWorld. A sessão desta loja foi preservada.",
        configured=_configured(store_profile_id),
    )


def get_login_session_status(store_profile_id: str) -> MakerWorldSessionStatus:
    session = _session(store_profile_id)
    if session:
        return session.status()
    configured = _configured(store_profile_id)
    if store_profile_id in _collect_endpoints:
        notice = _collect_notices.get(store_profile_id)
        return MakerWorldSessionStatus(
            open=False,
            configured=configured,
            mode="collect",
            attention=bool(notice),
            message=notice or "Conectando ao navegador da coleta...",
        )
    return MakerWorldSessionStatus(
        open=False,
        configured=configured,
        message="Sessão MakerWorld salva para esta loja." if configured else "Sessão MakerWorld ainda não configurada para esta loja.",
    )


def get_login_session_frame(store_profile_id: str, page_id: str | None = None) -> bytes | None:
    # Frames are only requested by an open panel, so this is where a collect viewer starts.
    session = _session(store_profile_id) or _collect_viewer(store_profile_id)
    if not session:
        return None
    if page_id and session.attached:
        return session.preview(page_id)
    return session.frame()


def send_login_session_input(store_profile_id: str, command: dict[str, Any]) -> None:
    session = _session(store_profile_id) or _collect_viewer(store_profile_id)
    if not session:
        raise RuntimeError("Navegador MakerWorld não está aberto")
    session.send(command)


def close_all_login_sessions() -> None:
    with _sessions_lock:
        sessions = list(_sessions.values())
    for session in sessions:
        session.close()
    deadline = time.monotonic() + 10
    for session in sessions:
        session._thread.join(timeout=max(0, deadline - time.monotonic()))


def active_login_sessions() -> int:
    with _sessions_lock:
        return sum(session._thread.is_alive() for session in _sessions.values())
