"""Limitadores de taxa globais e thread-safe (janela deslizante).

Os endpoints de geração rodam de forma síncrona no threadpool do FastAPI, então
várias requisições de lote podem executar em paralelo. Como cada produto dispara
múltiplas chamadas externas (a Kie cria uma task por prompt de imagem), o limite
precisa ficar na fronteira da chamada externa, e não por produto.

`acquire()` bloqueia a thread atual até existir uma vaga dentro da janela,
garantindo que nunca ultrapassamos `max_calls` chamadas em qualquer intervalo de
`period` segundos, independente de quantas threads estejam gerando ao mesmo tempo.
"""

import logging
import os
import threading
import time
from collections import deque

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_calls: int, period: float, name: str = "") -> None:
        if max_calls < 1:
            raise ValueError("max_calls deve ser >= 1")
        self.max_calls = max_calls
        self.period = period
        self.name = name or "rate_limiter"
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self, sleep=None) -> None:
        """Wait for a slot. A custom `sleep` is called in slices of at most 1s, so the
        caller can keep pumping its own events or stop while it waits."""
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                wait_for = self.period - (now - self._calls[0])
            if wait_for > 0:
                logger.debug("[%s] limite atingido, aguardando %.2fs", self.name, wait_for)
                if sleep is None:
                    time.sleep(min(wait_for, self.period))
                else:
                    sleep(min(wait_for, 1.0))


# Kie.ai: limite de 20 novas gerações por 10s. Usamos margem de segurança.
kie_generation_limiter = RateLimiter(max_calls=18, period=10.0, name="kie")

# OpenRouter: sem limite rígido, mas mantemos algo razoável.
openrouter_limiter = RateLimiter(max_calls=20, period=10.0, name="openrouter")

# MakerWorld: page loads from every collect browser leave the server through the same IP,
# so the pace is shared by all stores. Cloudflare challenges get more frequent above it.
makerworld_page_limiter = RateLimiter(
    max_calls=max(1, int(os.getenv("ECO_NATIVE_MAKERWORLD_PAGES_PER_MINUTE", "10"))),
    period=60.0,
    name="makerworld",
)

# Models read through MakerWorld's JSON routes (data + 3MF link + file each). Far faster than
# pages, so this pace is what keeps the store's account from downloading in bursts.
makerworld_api_limiter = RateLimiter(
    max_calls=max(1, int(os.getenv("ECO_NATIVE_MAKERWORLD_API_PER_MINUTE", "20"))),
    period=60.0,
    name="makerworld-api",
)
