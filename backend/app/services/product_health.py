from __future__ import annotations

from pathlib import Path

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
