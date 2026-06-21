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

    def acquire(self) -> None:
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
                time.sleep(min(wait_for, self.period))


# Kie.ai: limite de 20 novas gerações por 10s. Usamos margem de segurança.
kie_generation_limiter = RateLimiter(max_calls=18, period=10.0, name="kie")

# OpenRouter: sem limite rígido, mas mantemos algo razoável.
openrouter_limiter = RateLimiter(max_calls=20, period=10.0, name="openrouter")
