"""Scan studio.json for corrupted product cover images."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.paths import DB_PATH
from backend.app.services.cover_image import sniff_image_format


def main() -> None:
    data = json.loads(DB_PATH.read_text(encoding="utf-8"))
    bad: list[dict] = []
    for product in data.get("products", []):
        for asset in product.get("assets", []):
            if asset.get("kind") != "cover_image" or not asset.get("path"):
                continue
            path = Path(asset["path"])
            if not path.is_file():
                bad.append(
                    {
                        "sku": product.get("metadata", {}).get("sku"),
                        "path": str(path),
                        "fmt": "missing",
                    }
                )
                continue
            head = path.read_bytes()[:16]
            fmt = sniff_image_format(head)
            if fmt in {None, "gzip"}:
                bad.append(
                    {
                        "sku": product.get("metadata", {}).get("sku"),
                        "path": str(path),
                        "fmt": fmt,
                        "head": head.hex(),
                    }
                )

    print(f"DB: {DB_PATH}")
    print(f"Total products: {len(data.get('products', []))}")
    print(f"Bad covers: {len(bad)}")
    for item in bad[:20]:
        print(item)


if __name__ == "__main__":
    main()
