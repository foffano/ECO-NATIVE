from fastapi import APIRouter

from backend.app.services.runtime_status import get_exchange_status, has_internet

router = APIRouter()


@router.get("/status")
def read_runtime_status() -> dict:
    online = has_internet()
    exchange = get_exchange_status(allow_fetch=online)
    return {
        "online": online,
        "requires_internet": False,
        "exchange": exchange,
    }
