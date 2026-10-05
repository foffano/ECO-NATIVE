from __future__ import annotations

import time
from pathlib import Path
from threading import Lock

from backend.app.db.models import Product
from backend.app.services.product_paths import product_dir_for


def product_file_warnings(product: Product) -> list[str]:
    warnings: list[str] = []
    folder = product_dir_for(product)
    try:
        if folder.exists() and not any(folder.iterdir()):
            warnings.append("empty_folder")
    except OSError:
        warnings.append("folder_unreadable")

    for asset in product.assets:
        if not asset.path:
            continue
        if not Path(asset.path).is_file():
            warnings.append(f"missing_{asset.kind}")

    has_local_file = any(Path(asset.path).is_file() for asset in product.assets if asset.path)
    if not has_local_file and (
        product.metadata.get("image_url")
        or any(asset.public_url for asset in product.assets)
    ):
        warnings.append("remote_only")

    return warnings


# Listing the catalog would otherwise stat every asset of every product on each
# request. Saving a product changes updated_at, which invalidates its entry; the
# TTL covers files that disappear without the product being saved.
_WARNINGS_TTL_SECONDS = 60.0
_warnings_cache: dict[str, tuple[str, float, list[str]]] = {}
_warnings_lock = Lock()


def cached_product_file_warnings(product: Product) -> list[str]:
    now = time.monotonic()
    with _warnings_lock:
        cached = _warnings_cache.get(product.id)
    if cached and cached[0] == product.updated_at and now - cached[1] < _WARNINGS_TTL_SECONDS:
        return list(cached[2])
    warnings = product_file_warnings(product)
    with _warnings_lock:
        _warnings_cache[product.id] = (product.updated_at, now, warnings)
    return list(warnings)
