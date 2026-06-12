from __future__ import annotations

import shutil
from pathlib import Path

from backend.app.core.paths import PROJECTS_DIR
from backend.app.db.models import Product
from backend.app.services.cloudflare_r2 import delete_r2_keys, delete_r2_prefix, public_url_to_r2_key, r2_configured
from backend.app.services.product_paths import product_dir_for


def r2_key_prefix(product: Product) -> str:
    return f"eco-native/{product.project_id}/{product.id}"


def _path_within_projects(path: Path) -> bool:
    try:
        path.resolve().relative_to(PROJECTS_DIR.resolve())
        return True
    except ValueError:
        return False


def delete_local_product_files(product: Product) -> dict[str, list[str] | bool]:
    removed_files: list[str] = []
    folder = product_dir_for(product).resolve()
    projects_root = PROJECTS_DIR.resolve()
    folder_removed = False

    if folder.exists() and _path_within_projects(folder):
        shutil.rmtree(folder)
        folder_removed = True
        removed_files.append(str(folder))
    else:
        for asset in product.assets:
            asset_path = Path(asset.path).resolve()
            if asset_path.is_file() and _path_within_projects(asset_path):
                asset_path.unlink(missing_ok=True)
                removed_files.append(str(asset_path))

    return {"folder_removed": folder_removed, "paths": removed_files}


def delete_product_r2_files(product: Product) -> dict[str, int | list[str] | str]:
    if not r2_configured():
        return {"deleted": 0, "keys": [], "prefix": r2_key_prefix(product)}

    prefix = r2_key_prefix(product)
    deleted = delete_r2_prefix(prefix)

    legacy_keys: set[str] = set()
    for asset in product.assets:
        if not asset.public_url:
            continue
        key = public_url_to_r2_key(asset.public_url)
        if key and not key.startswith(f"{prefix}/"):
            legacy_keys.add(key)

    if legacy_keys:
        deleted += delete_r2_keys(sorted(legacy_keys))

    return {"deleted": deleted, "prefix": prefix, "legacy_keys": sorted(legacy_keys)}


def purge_product_data(product: Product) -> dict:
    local = delete_local_product_files(product)
    remote = delete_product_r2_files(product)
    return {"local": local, "r2": remote}
