"""Windowless Windows entry point with logs and single-instance protection."""
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys


def main() -> None:
    os.chdir(Path(__file__).resolve().parents[1])
    from backend.app.core.paths import DATA_DIR

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logs = DATA_DIR / "logs"
    logs.mkdir(exist_ok=True)
    # pythonw has no stdout/stderr; uvicorn and subprocess diagnostics need them.
    stream = open(logs / "background-console.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    handler = RotatingFileHandler(logs / "server.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if "--desktop-worker" in sys.argv:
        os.environ["ECO_NATIVE_PRIVATE_DESKTOP"] = "1"
        from backend.web_server import main as serve
        try:
            serve(log_config=None)
        except Exception:
            logging.exception("Private desktop server failed")
            raise
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, "Local\\ECO-Native-Studio-Web")
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        return
    try:
        from backend.app.core.windows_desktop import run_on_private_desktop
        result = run_on_private_desktop()
        if result:
            raise RuntimeError(f"Private desktop server exited with code {result}")
    except Exception:
        logging.exception("Background server failed")
        raise
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    main()
