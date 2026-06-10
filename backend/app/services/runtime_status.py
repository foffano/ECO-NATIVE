from __future__ import annotations

import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from backend.app.core.paths import CACHE_DIR

EXCHANGE_CACHE_PATH = CACHE_DIR / "exchange_usd_brl.json"
EXCHANGE_TTL = timedelta(hours=24)
EXCHANGE_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def has_internet(timeout: float = 3.0) -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=timeout).close()
        return True
    except OSError:
        return False


def read_exchange_cache() -> dict | None:
    if not EXCHANGE_CACHE_PATH.exists():
        return None
    try:
        return json.loads(EXCHANGE_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def cache_is_fresh(cache: dict | None) -> bool:
    fetched_at = parse_datetime(str(cache.get("fetched_at"))) if cache else None
    return bool(fetched_at and now_utc() - fetched_at < EXCHANGE_TTL)


def write_exchange_cache(payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    EXCHANGE_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_usd_brl_rate() -> dict:
    request = Request(EXCHANGE_URL, headers={"User-Agent": "ECO Native Studio/0.1"})
    with urlopen(request, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
    rate = float(data["USDBRL"]["bid"])
    return {
        "usd_brl": round(rate, 4),
        "fetched_at": now_utc().isoformat(),
        "source": "awesomeapi",
    }


def get_exchange_status(allow_fetch: bool = True) -> dict:
    cache = read_exchange_cache()
    if cache_is_fresh(cache):
        return {**cache, "cached": True, "stale": False, "cache_path": str(EXCHANGE_CACHE_PATH)}

    if not allow_fetch:
        if cache:
            return {**cache, "cached": True, "stale": True, "cache_path": str(EXCHANGE_CACHE_PATH)}
        return {
            "usd_brl": None,
            "fetched_at": None,
            "source": None,
            "cached": False,
            "stale": True,
            "cache_path": str(EXCHANGE_CACHE_PATH),
        }

    try:
        payload = fetch_usd_brl_rate()
        write_exchange_cache(payload)
        return {**payload, "cached": False, "stale": False, "cache_path": str(EXCHANGE_CACHE_PATH)}
    except (OSError, URLError, KeyError, ValueError, TimeoutError):
        if cache:
            return {**cache, "cached": True, "stale": True, "cache_path": str(EXCHANGE_CACHE_PATH)}
        return {
            "usd_brl": None,
            "fetched_at": None,
            "source": None,
            "cached": False,
            "stale": True,
            "cache_path": str(EXCHANGE_CACHE_PATH),
        }
