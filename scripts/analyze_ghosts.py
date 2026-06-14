#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
studio = json.loads((ROOT / "data/studio.json").read_text(encoding="utf-8"))
products = studio.get("products", [])


def safe_sku_folder(sku: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", sku.strip()).strip()
    return cleaned[:120] or "SEM-SKU"


print(f"Total products: {len(products)}")

for p in products:
    pid = p.get("project_id")
    sku = p.get("metadata", {}).get("sku") or p.get("sku")
    if not pid:
        continue

    folder = None
    if sku:
        folder = ROOT / "data/projects" / pid / safe_sku_folder(str(sku))

    assets = p.get("assets", [])
    cover = next((a for a in assets if a.get("kind") == "cover_image"), None)

    folder_exists = folder.exists() if folder else False
    folder_has_files = folder_exists and any(folder.iterdir()) if folder_exists else False

    path_exists = bool(cover and cover.get("path") and Path(cover["path"]).exists())
    public_url = cover.get("public_url") if cover else None
    meta_url = p.get("metadata", {}).get("image_url")

    missing_local = cover and (public_url or meta_url) and not path_exists
    empty_folder = folder_exists and not folder_has_files

    if missing_local or empty_folder or (cover and not path_exists):
        print("---")
        print("id:", p["id"])
        print("name:", p["name"][:60])
        print("sku:", sku)
        print("folder:", folder)
        print("folder_exists:", folder_exists, "has_files:", folder_has_files)
        if cover:
            print("path:", cover.get("path"))
            print("path_exists:", path_exists)
            print("public_url:", (public_url or "")[:100])
        print("meta_url:", (meta_url or "")[:100] if meta_url else None)
