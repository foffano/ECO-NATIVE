"""Repair missing or corrupted product cover images in studio.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.paths import DB_PATH
from backend.app.db.models import StudioState
from backend.app.db.store import store
from backend.app.services.cover_image import repair_all_product_covers, sniff_image_format


def main() -> None:
    state = store.load()
    products_with_cover = [
        product
        for product in state.products
        if any(asset.kind == "cover_image" for asset in product.assets)
    ]
    print(f"DB: {DB_PATH}")
    print(f"Produtos com capa: {len(products_with_cover)}")

    suspicious = 0
    for product in products_with_cover:
        cover = next(asset for asset in product.assets if asset.kind == "cover_image")
        if not cover.path:
            suspicious += 1
            continue
        path = Path(cover.path)
        if not path.is_file():
            suspicious += 1
            continue
        if sniff_image_format(path.read_bytes()[:16]) in {None, "gzip"}:
            suspicious += 1
    print(f"Capas suspeitas antes do reparo: {suspicious}")

    result = repair_all_product_covers(products_with_cover)
    for product in products_with_cover:
        store.upsert_product(product)

    print(f"Reparadas: {result['repaired']}")
    print(f"Falhas: {result['failed_count']}")
    for item in result["failed"][:20]:
        print(f"  - {item}")


if __name__ == "__main__":
    main()
