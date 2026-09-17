"""Prevent multiple Linux API workers from sharing the JSON data directory."""
import os
from contextlib import contextmanager

from backend.app.core.paths import DATA_DIR


@contextmanager
def server_lock():
    if os.name != "posix":
        yield
        return
    import fcntl
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / ".server.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Diretório de dados em uso. Execute apenas uma instância e um worker Uvicorn.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
