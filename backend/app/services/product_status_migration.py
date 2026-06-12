from __future__ import annotations

from backend.app.db.models import ProductStatus, StudioState

LEGACY_PRODUCT_STATUS_MAP: dict[str, str] = {
    "imported": ProductStatus.collected.value,
    "scraped": ProductStatus.collected.value,
    "ai_approved": ProductStatus.collected.value,
    "assets_downloaded": ProductStatus.collected.value,
    "failed": ProductStatus.collected.value,
    "listing_generated": ProductStatus.in_edit.value,
    "needs_review": ProductStatus.in_edit.value,
    "images_generated": ProductStatus.in_edit.value,
    "approved": ProductStatus.ready.value,
    "exported": ProductStatus.exported.value,
}

VALID_PRODUCT_STATUSES = {status.value for status in ProductStatus}


def normalize_product_status(raw_status: str | None) -> str:
    if not raw_status:
        return ProductStatus.collected.value
    if raw_status in VALID_PRODUCT_STATUSES:
        return raw_status
    return LEGACY_PRODUCT_STATUS_MAP.get(raw_status, ProductStatus.collected.value)


def migrate_product_status_payload(data: dict) -> tuple[dict, bool]:
    changed = False
    for product in data.get("products", []):
        current = product.get("status")
        normalized = normalize_product_status(current if isinstance(current, str) else None)
        if current != normalized:
            product["status"] = normalized
            changed = True
    return data, changed


def migrate_product_statuses(state: StudioState) -> bool:
    changed = False
    for product in state.products:
        current = product.status.value if isinstance(product.status, ProductStatus) else str(product.status)
        normalized = normalize_product_status(current)
        if current != normalized:
            product.status = ProductStatus(normalized)
            changed = True
    return changed
