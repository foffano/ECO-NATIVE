from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.db.store import store
from backend.app.services.auth import list_auth_users, update_store_access
from backend.app.services.authorization import require_admin
from backend.app.services.usage_limits import QUOTA_KEYS, available_periods, current_month, store_usage

router = APIRouter()


class StoreLimitsUpdate(BaseModel):
    enabled: bool = True
    collect_monthly: int | None = Field(default=None, ge=0)
    listing_monthly: int | None = Field(default=None, ge=0)
    image_monthly: int | None = Field(default=None, ge=0)
    ai_cost_usd_monthly: float | None = Field(default=None, ge=0)


def _admin_store_rows(period: str) -> list[dict]:
    state = store.load()
    users = list_auth_users()
    rows = []
    for profile in state.store_profiles:
        access = next(
            (item for item in users if item.get("role") == "store" and item.get("store_profile_id") == profile.id),
            None,
        )
        rows.append({
            "store": {"id": profile.id, "name": profile.name, "marketplace": profile.marketplace},
            "username": access.get("username") if access else None,
            "enabled": bool(access.get("enabled", True)) if access else False,
            "quotas": dict(access.get("quotas") or {}) if access else {},
            "usage": store_usage(state, profile.id, period),
        })
    return rows


@router.get("/usage")
def admin_usage(request: Request, period: str | None = None) -> dict:
    require_admin(request)
    state = store.load()
    periods = available_periods(state)
    selected = period or current_month()
    if selected != "all" and selected not in periods and selected != current_month():
        raise HTTPException(status_code=400, detail="Período inválido")
    rows = _admin_store_rows(selected)
    totals = {key: round(sum(float(row["usage"].get(key, 0)) for row in rows), 6) for key in QUOTA_KEYS}
    return {
        "period": selected,
        "periods": list(dict.fromkeys([current_month(), *periods])),
        "totals": totals,
        "stores": rows,
    }


@router.put("/stores/{store_profile_id}/limits")
def update_limits(store_profile_id: str, payload: StoreLimitsUpdate, request: Request) -> dict:
    require_admin(request)
    try:
        update_store_access(
            store_profile_id,
            enabled=payload.enabled,
            quotas={key: getattr(payload, key) for key in QUOTA_KEYS},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return next(row for row in _admin_store_rows(current_month()) if row["store"]["id"] == store_profile_id)

