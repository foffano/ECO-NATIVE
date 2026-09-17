"""Single-process leases for persistent Chromium profiles and browser capacity."""
import os
import threading
from contextlib import contextmanager

_guard = threading.Lock()
_profiles: set[str] = set()


@contextmanager
def browser_lease(profile: str):
    with _guard:
        if profile in _profiles:
            raise RuntimeError("Navegador desta loja em uso. Feche o login MakerWorld ou aguarde a coleta terminar.")
        if len(_profiles) >= max(1, int(os.getenv("ECO_NATIVE_MAX_BROWSERS", "2"))):
            raise RuntimeError("Limite de navegadores atingido. Feche uma sessão ou aguarde a coleta terminar.")
        _profiles.add(profile)
    try:
        yield
    finally:
        with _guard:
            _profiles.discard(profile)
