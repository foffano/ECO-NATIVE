import queue
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import sync_playwright

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


class RemoteBrowserSession:
    def __init__(self, store_profile_id: str) -> None:
        self.store_profile_id = store_profile_id
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._url: str | None = None
        self._error: str | None = None
        self._open = False
        self._last_activity = time.monotonic()
        self._thread = threading.Thread(target=self._run, name=f"makerworld-{store_profile_id[:8]}", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def status(self) -> MakerWorldSessionStatus:
        with self._lock:
            is_open = self._open and self._thread.is_alive()
            url = self._url
            error = self._error
        configured = _configured(self.store_profile_id)
        if error:
            message = f"Falha no navegador MakerWorld: {error}"
        elif is_open:
            message = (
                "Navegador MakerWorld oculto no servidor e disponível para controle remoto."
                if os.getenv("ECO_NATIVE_PRIVATE_DESKTOP") == "1"
                else "Navegador MakerWorld visível no PC e disponível para controle remoto."
            )
        elif configured:
            message = "Sessão MakerWorld salva para esta loja."
        else:
            message = "Sessão MakerWorld ainda não configurada para esta loja."
        return MakerWorldSessionStatus(open=is_open, url=url, message=message, configured=configured)

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
            with sync_playwright() as playwright:
                context = open_makerworld_context(
                    playwright,
                    headless=False,
                    store_profile_id=self.store_profile_id,
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(os.getenv("ECO_NATIVE_MAKERWORLD_URL", MAKERWORLD_HOME), wait_until="domcontentloaded", timeout=60_000)
                with self._lock:
                    self._open = True
                running = True
                while running and context.pages:
                    if time.monotonic() - self._last_activity > SESSION_IDLE_SECONDS:
                        break
                    page = context.pages[-1]
                    while True:
                        try:
                            running = self._execute(page, self.commands.get_nowait())
                            if not running:
                                break
                        except queue.Empty:
                            break
                    if not running:
                        break
                    try:
                        frame = page.screenshot(type="jpeg", quality=68, animations="disabled", timeout=5_000)
                        with self._lock:
                            self._frame = frame
                            self._url = page.url
                    except Exception:
                        pass
                    time.sleep(FRAME_INTERVAL_SECONDS)
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
    existing = _session(store_profile_id)
    if existing:
        existing.send({"type": "move", "x": 0, "y": 0})
        return existing.status()
    session = RemoteBrowserSession(store_profile_id)
    with _sessions_lock:
        _sessions[store_profile_id] = session
    session.start()
    return MakerWorldSessionStatus(
        open=True,
        message="Iniciando navegador MakerWorld visível no PC...",
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
