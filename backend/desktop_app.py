"""macOS app: serves the API in this process and shows it in a native window.

The window is WebKit (pywebview) showing the same React interface the browser loads.
The API listens on 127.0.0.1 only. Closing the window stops the server, the job queue
and the MakerWorld browsers; work still running is marked as failed on the next start,
as after any restart.

Run from the repository with `npm run desktop:mac`; package it with
`scripts/build_macos_app.sh`.
"""
import json
import logging
import os
import plistlib
import socket
import sys
import threading
import time
from html import escape
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = "ECO Native Studio"
HOST = "127.0.0.1"
# The web server's 18765 is often held on this Mac by an SSH tunnel to the VPS.
DEFAULT_PORT = 18766
WINDOW_BACKGROUND = "#f4f8f0"
STARTUP_TIMEOUT_SECONDS = 90
SHUTDOWN_TIMEOUT_SECONDS = 25

PT_BR = {
    "global.quitConfirmation": "Deseja realmente sair?",
    "global.ok": "OK",
    "global.quit": "Sair",
    "global.cancel": "Cancelar",
    "global.saveFile": "Salvar arquivo",
    "cocoa.menu.about": "Sobre",
    "cocoa.menu.services": "Serviços",
    "cocoa.menu.view": "Visualizar",
    "cocoa.menu.edit": "Editar",
    "cocoa.menu.hide": "Ocultar",
    "cocoa.menu.hideOthers": "Ocultar Outros",
    "cocoa.menu.showAll": "Mostrar Tudo",
    "cocoa.menu.quit": "Encerrar",
    "cocoa.menu.fullscreen": "Entrar em Tela Cheia",
    "cocoa.menu.cut": "Recortar",
    "cocoa.menu.copy": "Copiar",
    "cocoa.menu.paste": "Colar",
    "cocoa.menu.selectAll": "Selecionar Tudo",
}


def bundle_contents() -> Path | None:
    """Contents folder of the packaged app; None when running from the repository."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parents[1]


def bundled_browsers_dir() -> Path | None:
    """Chromium that the build script puts in Contents/Resources of the app."""
    contents = bundle_contents()
    candidate = contents / "Resources" / "playwright-browsers" if contents else None
    return candidate if candidate and candidate.is_dir() else None


def use_bundle_version() -> None:
    """Report the app's version in /health, as the Docker image does."""
    contents = bundle_contents()
    if not contents:
        return
    try:
        with (contents / "Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return
    os.environ.setdefault("ECO_NATIVE_VERSION", str(info.get("CFBundleShortVersionString") or "dev"))
    os.environ.setdefault("ECO_NATIVE_REVISION", str(info.get("ECONativeRevision") or "unknown"))


def choose_port(preferred: int, host: str = HOST) -> int:
    """The preferred port when it is free, otherwise any free port."""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return probe.getsockname()[1]
    raise RuntimeError(f"Nenhuma porta livre em {host}.")


def configure_logging(data_dir: Path) -> Path:
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(logs / "server.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    ]
    if getattr(sys, "frozen", False):
        # Opened from Finder there is no terminal; keep tracebacks and subprocess output.
        stream = open(logs / "desktop-console.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = stream
    else:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    return logs


def start_server(port: int):
    """Run Uvicorn in a thread and return once the app finished starting."""
    import uvicorn
    from backend.app.main import app

    config = uvicorn.Config(
        app,
        host=HOST,
        port=port,
        log_config=None,
        log_level="info",
        # An open MakerWorld viewer socket must not hold up quitting.
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="eco-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("A API local não iniciou. Outra cópia do ECO Native pode estar usando os mesmos dados.")
        if time.monotonic() > deadline:
            server.should_exit = True
            raise RuntimeError("A API local não iniciou dentro do tempo esperado.")
        time.sleep(0.1)
    return server, thread


def stop_server(server, thread: threading.Thread, timeout: float = SHUTDOWN_TIMEOUT_SECONDS) -> None:
    """Run the app's shutdown: the MakerWorld browsers save their cookies, the queue stops."""
    server.should_exit = True
    thread.join(timeout)
    if thread.is_alive():
        logging.warning("Server still stopping after %ss; quitting anyway", timeout)


def active_jobs() -> int:
    try:
        from backend.app.db.models import JobStatus
        from backend.app.db.store import store

        return sum(1 for job in store.load().jobs if job.status in {JobStatus.queued, JobStatus.running})
    except Exception:
        logging.exception("Could not count running jobs")
        return 0


def confirm_close() -> bool:
    """Ask before quitting while jobs run. pywebview calls this on the main thread."""
    count = active_jobs()
    if not count:
        return True
    import AppKit

    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_("Encerrar o ECO Native Studio?")
    alert.setInformativeText_(
        f"{count} trabalho(s) em andamento serão interrompidos e ficarão como falha para revisão."
    )
    alert.addButtonWithTitle_("Encerrar")
    alert.addButtonWithTitle_("Continuar aberto")
    alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
    return alert.runModal() == AppKit.NSAlertFirstButtonReturn


def startup_error_page(message: str, logs: Path) -> str:
    return (
        "<!doctype html><html lang='pt-BR'><body style=\"font-family:-apple-system,sans-serif;"
        f"background:{WINDOW_BACKGROUND};color:#1f2a24;padding:40px;line-height:1.5\">"
        "<h2 style='margin-top:0'>Não foi possível abrir o ECO Native Studio</h2>"
        f"<p>{escape(message)}</p>"
        f"<p style='color:#5f7167'>Logs: {escape(str(logs))}</p></body></html>"
    )


def self_test() -> int:
    """Checks a packaged app can start Chromium and find the CLIs; used by the build script."""
    import shutil

    from backend.app.core.playwright_env import configure_playwright_browsers

    report: dict[str, object] = {"browsers": os.environ.get("PLAYWRIGHT_BROWSERS_PATH")}
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = configure_playwright_browsers(playwright)
            browser = playwright.chromium.launch(headless=False, executable_path=str(executable) if executable else None)
            report["chromium"] = browser.version
            browser.close()
    except Exception as exc:
        report["chromium_error"] = f"{exc.__class__.__name__}: {exc}"
    report["codex"] = shutil.which("codex")
    report["claude"] = shutil.which("claude")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if "chromium" in report else 1


def main() -> int:
    browsers = bundled_browsers_dir()
    if browsers:
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers))
    use_bundle_version()
    from backend.app.core.shell_path import use_login_shell_path

    use_login_shell_path()
    if "--self-test" in sys.argv:
        return self_test()

    from backend.app.core.paths import DATA_DIR

    logs = configure_logging(DATA_DIR)
    import webview

    webview.settings["ALLOW_DOWNLOADS"] = True
    try:
        port = choose_port(int(os.getenv("ECO_NATIVE_PORT") or DEFAULT_PORT))
        server, thread = start_server(port)
    except Exception as exc:
        logging.exception("Desktop startup failed")
        webview.create_window(APP_NAME, html=startup_error_page(str(exc), logs), width=640, height=320)
        webview.start(localization=PT_BR)
        return 1

    logging.info("ECO Native Studio at http://%s:%s, data in %s", HOST, port, DATA_DIR)
    logging.info("PATH for command-line tools: %s", os.environ.get("PATH"))

    def on_closing() -> bool:
        # Cmd+Q ends the process as soon as this returns, so the server stops here.
        if not confirm_close():
            return False
        stop_server(server, thread)
        return True

    window = webview.create_window(
        APP_NAME,
        f"http://{HOST}:{port}/",
        width=1400,
        height=900,
        min_size=(1100, 700),
        background_color=WINDOW_BACKGROUND,
        text_select=True,
        zoomable=True,
    )
    window.events.closing += on_closing
    webview.start(
        localization=PT_BR,
        private_mode=False,
        debug=os.getenv("ECO_NATIVE_WEBVIEW_DEBUG") == "1",
    )
    stop_server(server, thread)
    return 0


if __name__ == "__main__":
    sys.exit(main())
