import os
import signal
import subprocess
import sys
from dataclasses import dataclass

from backend.app.core.paths import DATA_DIR

PID_FILE = DATA_DIR / "makerworld_login.pid"
PROJECT_ROOT = DATA_DIR.parent if (DATA_DIR.parent / "backend").exists() else None


@dataclass
class MakerWorldSessionStatus:
    open: bool
    url: str | None = None
    message: str = ""


def _read_pid() -> int | None:
    try:
        if not PID_FILE.exists():
            return None
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def open_login_session() -> MakerWorldSessionStatus:
    existing_pid = _read_pid()
    if existing_pid and _is_process_running(existing_pid):
        return MakerWorldSessionStatus(
            open=True,
            message="Sessão MakerWorld já está aberta em uma janela separada.",
        )

    process = subprocess.Popen(
        [sys.executable, "-m", "backend.app.services.makerworld_login_window"],
        cwd=str(PROJECT_ROOT) if PROJECT_ROOT else None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")

    return MakerWorldSessionStatus(
        open=True,
        message="Janela MakerWorld aberta. Faça login e conclua qualquer verificação; os cookies serão salvos automaticamente.",
    )


def close_login_session() -> MakerWorldSessionStatus:
    pid = _read_pid()
    if pid and _is_process_running(pid):
        try:
            if os.name == "nt":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    return MakerWorldSessionStatus(open=False, message="Sessão MakerWorld fechada.")


def get_login_session_status() -> MakerWorldSessionStatus:
    pid = _read_pid()
    if pid and _is_process_running(pid):
        return MakerWorldSessionStatus(open=True, message="Sessão MakerWorld aberta.")
    return MakerWorldSessionStatus(open=False, message="Sessão MakerWorld fechada.")
