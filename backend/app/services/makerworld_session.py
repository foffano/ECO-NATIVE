from contextlib import ExitStack
import queue
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import sync_playwright, Error as PlaywrightError

from backend.app.services.makerworld_scraper import MAKERWORLD_HOME, makerworld_profile_dir, open_makerworld_context


VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
FRAME_INTERVAL_SECONDS = 0.45
SESSION_IDLE_SECONDS = 30 * 60


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


class BrowserPages:
    """Track popup lifetime independently of context.pages ordering."""
    def __init__(self, context):
        self.pages = {}
        self.active_id = None
        self._next_id = 0
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

    def remove(self, key):
        self.pages.pop(key, None)
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
    def __init__(self, store_profile_id: str) -> None:
        self.store_profile_id = store_profile_id
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._url: str | None = None
        self._error: str | None = None
        self._open = False
        self._pages = []
        self._active_page_id = None
        self._last_activity = time.monotonic()
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
        configured = _configured(self.store_profile_id)
        if error:
            message = f"Falha no navegador MakerWorld: {error}"
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
                                       pages=pages, active_page_id=active_page_id)

    def frame(self) -> bytes | None:
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
            page.mouse.click(
                max(0, min(VIEWPORT_WIDTH, float(command.get("x", 0)))),
                max(0, min(VIEWPORT_HEIGHT, float(command.get("y", 0)))),
                button=command.get("button", "left"),
            )
        elif kind == "move":
            page.mouse.move(float(command.get("x", 0)), float(command.get("y", 0)))
        elif kind == "wheel":
            page.mouse.wheel(float(command.get("delta_x", 0)), float(command.get("delta_y", 0)))
        elif kind == "text":
            page.keyboard.insert_text(str(command.get("text", ""))[:2000])
        elif kind == "key":
            key = str(command.get("key", ""))[:80]
            if key:
                page.keyboard.press(key)
        return True

    def _run(self) -> None:
        try:
            with sync_playwright() as playwright, ExitStack() as contexts:
                context = contexts.enter_context(open_makerworld_context(
                    playwright,
                    headless=False,
                    store_profile_id=self.store_profile_id,
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                ))
                windows = BrowserPages(context)
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
                        with self._lock:
                            if windows.active_id == page_id and not page.is_closed():
                                self._frame = frame
                                self._url = page.url
                                self._active_page_id = page_id
                                self._error = None
                            self._pages = windows.describe()
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


_sessions: dict[str, RemoteBrowserSession] = {}
_sessions_lock = threading.Lock()


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


def open_login_session(store_profile_id: str) -> MakerWorldSessionStatus:
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
    return MakerWorldSessionStatus(
        open=False,
        configured=configured,
        message="Sessão MakerWorld salva para esta loja." if configured else "Sessão MakerWorld ainda não configurada para esta loja.",
    )


def get_login_session_frame(store_profile_id: str) -> bytes | None:
    session = _session(store_profile_id)
    return session.frame() if session else None


def send_login_session_input(store_profile_id: str, command: dict[str, Any]) -> None:
    session = _session(store_profile_id)
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
