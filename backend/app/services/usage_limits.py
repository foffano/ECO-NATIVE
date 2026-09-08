from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from backend.app.db.models import StudioState
from backend.app.services.auth import list_auth_users
from backend.app.services.authorization import store_project_ids

QUOTA_KEYS = {
    "collect_monthly": "coletas mensais",
    "listing_monthly": "textos mensais",
    "image_monthly": "operações de imagem mensais",
    "ai_cost_usd_monthly": "custo mensal de IA",
}


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _period(value: object) -> str:
    text = str(value or "")
    return text[:7] if len(text) >= 7 and text[4:5] == "-" else "legacy"


def available_periods(state: StudioState) -> list[str]:
    periods = {_period(job.created_at) for job in state.jobs}
    for product in state.products:
        events = product.metadata.get("cost_events") or []
        if events:
            periods.update(_period(event.get("created_at")) for event in events if isinstance(event, dict))
        elif product.metadata.get("cost_total_usd"):
            periods.add("legacy")
    periods.discard("legacy")
    return sorted(periods, reverse=True) + (["legacy"] if "legacy" in periods else [])


def store_usage(state: StudioState, store_profile_id: str, period: str | None = None) -> dict[str, int | float]:
    projects = store_project_ids(state, store_profile_id)
    products = [product for product in state.products if product.project_id in projects]
    product_ids = {product.id for product in products}
    selected = period or current_month()
    jobs = [
        job for job in state.jobs
        if (job.project_id in projects or job.product_id in product_ids)
        and str(job.status) != "failed"
        and (selected == "all" or _period(job.created_at) == selected)
    ]
    cost = 0.0
    for product in products:
        events = product.metadata.get("cost_events") or []
        if events:
            for event in events:
                if isinstance(event, dict) and (selected == "all" or _period(event.get("created_at")) == selected):
                    cost += float(event.get("cost_usd") or 0)
        elif product.metadata.get("cost_total_usd") and selected in {"all", "legacy"}:
            cost += float(product.metadata.get("cost_total_usd") or 0)
    return {
        "collect_monthly": sum(job.type == "collect_products" for job in jobs),
        "listing_monthly": sum(job.type == "generate_listing" for job in jobs),
        "image_monthly": sum(job.type in {"generate_images", "regenerate_image"} for job in jobs),
        "ai_cost_usd_monthly": round(cost, 6),
    }


def store_access(store_profile_id: str) -> dict:
    return next(
        (
            user for user in list_auth_users()
            if user.get("role") == "store" and user.get("store_profile_id") == store_profile_id
        ),
        {"enabled": False, "quotas": {}},
    )


def enforce_quota(state: StudioState, store_profile_id: str, quota_key: str) -> None:
    access = store_access(store_profile_id)
    if not access.get("enabled", True):
        raise HTTPException(status_code=403, detail="O acesso desta loja está bloqueado")
    limit = (access.get("quotas") or {}).get(quota_key)
    if limit is None:
        return
    used = store_usage(state, store_profile_id, current_month()).get(quota_key, 0)
    if float(used) >= float(limit):
        raise HTTPException(status_code=429, detail=f"Limite de {QUOTA_KEYS[quota_key]} atingido")
