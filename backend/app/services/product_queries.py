"""Server-side catalog filtering, pagination and statistics.

The predicates mirror the frontend's former in-memory filter (filterProducts
in src/main.tsx), so moving the work to the server keeps the same results.
"""

import base64
import binascii
import json
import re
from collections.abc import Iterable
from threading import Lock

from backend.app.db.models import Asset, Product
from backend.app.services.product_health import cached_product_file_warnings

CHARACTERISTICS = {
    "all",
    "with_listing",
    "without_listing",
    "with_image",
    "without_image",
    "with_model",
    "without_model",
    "listed",
    "not_listed",
    "draft_listing",
    "without_ai_images",
    "file_issues",
}
PUBLICATIONS = {"all", "listed", "not_listed"}
PREVIOUS_VERSION_PREFIX = "previous_"
_IMAGE_SUFFIX = re.compile(r"\.(png|jpe?g|webp)$", re.IGNORECASE)

_search_cache: dict[str, tuple[str, str]] = {}
_search_cache_lock = Lock()


def is_image_asset(asset: Asset) -> bool:
    if asset.kind.startswith(PREVIOUS_VERSION_PREFIX):
        return False
    return "image" in asset.kind or bool(_IMAGE_SUFFIX.search(asset.path or ""))


def is_model_asset(asset: Asset) -> bool:
    return asset.kind == "model_3mf" or asset.kind.startswith("model_3mf_extra")


def has_listing(product: Product) -> bool:
    return bool(product.listing.title or product.listing.description)


def has_draft_listing(product: Product) -> bool:
    """Started but missing the title or the description."""
    return has_listing(product) and not (product.listing.title and product.listing.description)


def has_ai_images(product: Product) -> bool:
    return any(asset.kind.startswith(("generated_", "color_")) for asset in product.assets)


def _status(product: Product) -> str:
    return str(product.status.value if hasattr(product.status, "value") else product.status)


def board_stage(product: Product) -> str:
    """The board column: published products leave their status column."""
    return "listed" if is_listed(product) else _status(product)


def is_listed(product: Product) -> bool:
    return bool(product.metadata.get("listed"))


def _color_skus(product: Product) -> list[str]:
    value = product.metadata.get("color_skus")
    return [str(item) for item in value.values()] if isinstance(value, dict) else []


def _search_text(product: Product) -> str:
    with _search_cache_lock:
        cached = _search_cache.get(product.id)
    if cached and cached[0] == product.updated_at:
        return cached[1]
    text = " ".join(
        [
            product.name,
            product.source_url or "",
            str(product.status.value if hasattr(product.status, "value") else product.status),
            " ".join(product.tags),
            product.listing.title,
            product.listing.category,
            " ".join(product.listing.keywords),
            str(product.metadata.get("sku") or ""),
            " ".join(_color_skus(product)),
            "a venda à venda vendido publicado" if is_listed(product) else "nao esta a venda não está à venda",
        ]
    ).lower()
    with _search_cache_lock:
        _search_cache[product.id] = (product.updated_at, text)
    return text


def product_matches(product: Product, *, query: str = "", status: str = "all", characteristic: str = "all") -> bool:
    if status != "all" and product.status != status:
        return False
    query = query.strip().lower()
    if query and query not in _search_text(product):
        return False
    if characteristic == "with_listing":
        return has_listing(product)
    if characteristic == "without_listing":
        return not has_listing(product)
    if characteristic == "with_image":
        return any(is_image_asset(asset) for asset in product.assets)
    if characteristic == "without_image":
        return not any(is_image_asset(asset) for asset in product.assets)
    if characteristic == "with_model":
        return any(is_model_asset(asset) for asset in product.assets)
    if characteristic == "without_model":
        return not any(is_model_asset(asset) for asset in product.assets)
    if characteristic == "listed":
        return is_listed(product)
    if characteristic == "not_listed":
        return not is_listed(product)
    if characteristic == "draft_listing":
        return has_draft_listing(product)
    if characteristic == "without_ai_images":
        return not has_ai_images(product)
    if characteristic == "file_issues":
        return bool(cached_product_file_warnings(product))
    return True


def _sort_key(product: Product) -> tuple[str, str]:
    return product.created_at, product.id


def encode_cursor(product: Product) -> str:
    raw = json.dumps(list(_sort_key(product))).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        created_at, product_id = json.loads(raw)
    except (binascii.Error, ValueError, TypeError) as error:
        raise ValueError("Cursor inválido") from error
    return str(created_at), str(product_id)


def page_products(products: Iterable[Product], *, limit: int, cursor: str | None = None) -> tuple[list[Product], str | None]:
    """Newest first. The cursor is the sort key of the last item returned, so
    products added or removed between requests never shift the next page."""
    ordered = sorted(products, key=_sort_key, reverse=True)
    if cursor:
        after = decode_cursor(cursor)
        ordered = [product for product in ordered if _sort_key(product) < after]
    page = ordered[:limit]
    next_cursor = encode_cursor(page[-1]) if len(ordered) > limit else None
    return page, next_cursor


def product_cost_total(product: Product) -> float:
    try:
        stored = float(product.metadata.get("cost_total_usd") or 0)
    except (TypeError, ValueError):
        stored = 0.0
    if stored > 0:
        return stored
    return sum(_event_cost(event) for event in _cost_events(product))


def _cost_events(product: Product) -> list[dict]:
    events = product.metadata.get("cost_events")
    return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []


def _event_cost(event: dict) -> float:
    try:
        return float(event.get("cost_usd") or 0)
    except (TypeError, ValueError):
        return 0.0


def catalog_stats(products: list[Product]) -> dict:
    by_provider = {"openrouter": 0.0, "kie": 0.0, "other": 0.0}
    for product in products:
        for event in _cost_events(product):
            provider = str(event.get("provider") or "").lower()
            key = "openrouter" if "openrouter" in provider else "kie" if "kie" in provider else "other"
            by_provider[key] += _event_cost(event)
    stages = {"collected": 0, "in_edit": 0, "ready": 0, "exported": 0, "listed": 0}
    for product in products:
        stage = board_stage(product)
        if stage in stages:
            stages[stage] += 1
    # Only products still to be published need work.
    pending = [product for product in products if not is_listed(product)]
    costs = [product_cost_total(product) for product in products]
    return {
        "total": len(products),
        "stages": stages,
        "attention": {
            "without_listing": sum(1 for product in pending if not has_listing(product)),
            "draft_listing": sum(1 for product in pending if has_draft_listing(product)),
            "without_ai_images": sum(1 for product in pending if not has_ai_images(product)),
            "without_model": sum(1 for product in pending if not any(is_model_asset(asset) for asset in product.assets)),
            "file_issues": sum(1 for product in products if cached_product_file_warnings(product)),
        },
        "ai_cost_usd": sum(costs),
        "ai_cost_products": sum(1 for cost in costs if cost > 0),
        "ai_cost_by_provider": by_provider,
    }
