from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

from backend.app.core.paths import PROJECTS_DIR
from backend.app.db.models import PendingCleanup, Product, StudioState
from backend.app.db.store import store
from backend.app.services.cloudflare_r2 import delete_r2_keys, delete_r2_prefix, public_url_to_r2_key, r2_configured
from backend.app.services.product_paths import product_dir_for

logger = logging.getLogger(__name__)


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


def purge_product_data(product: Product, *, keep_local: bool = False) -> dict:
    result: dict = {"local": None, "r2": None, "errors": []}

    try:
        if not keep_local:
            result["local"] = delete_local_product_files(product)
    except Exception as exc:
        logger.warning("Falha ao apagar arquivos locais do produto %s: %s", product.id, exc)
        result["errors"].append(f"local: {exc}")

    try:
        result["r2"] = delete_product_r2_files(product)
    except Exception as exc:
        logger.warning("Falha ao apagar arquivos R2 do produto %s: %s", product.id, exc)
        result["errors"].append(f"r2: {exc}")

    return result


# Deleted products wait in the store until their files are gone, so a restart
# in between resumes the cleanup instead of leaving orphan files behind.
_cleanup_running = threading.Lock()
_cleanup_requested = threading.Event()


def queue_product_cleanup(state: StudioState, products: list[Product]) -> None:
    """Record the files to remove, in the same write that removes the products."""
    queued = {entry.id for entry in state.pending_cleanups}
    state.pending_cleanups.extend(
        PendingCleanup(id=product.id, product=product) for product in products if product.id not in queued
    )


def run_pending_cleanups() -> None:
    """Remove the queued files; a call during a running pass makes it run again."""
    _cleanup_requested.set()
    while _cleanup_requested.is_set():
        if not _cleanup_running.acquire(blocking=False):
            return
        try:
            _cleanup_requested.clear()
            _cleanup_pass()
        except Exception:
            logger.exception("Falha na limpeza de arquivos de produtos apagados")
        finally:
            _cleanup_running.release()


def _cleanup_pass() -> None:
    state = store.snapshot()
    entries = list(state.pending_cleanups)
    if not entries:
        return
    live_ids = {product.id for product in state.products}
    # SKU folders can be reused by a product created after the deletion.
    live_folders = {product_dir_for(product).resolve() for product in state.products}
    finished: set[str] = set()
    failed: dict[str, str] = {}
    for entry in entries:
        if entry.id in live_ids:
            # Brought back (e.g. by a backup restore): its files are in use again.
            finished.add(entry.id)
            continue
        keep_local = product_dir_for(entry.product).resolve() in live_folders
        if keep_local:
            logger.warning("Pasta de %s mantida: outro produto usa a mesma pasta.", entry.id)
        result = purge_product_data(entry.product, keep_local=keep_local)
        if result["errors"]:
            failed[entry.id] = "; ".join(result["errors"])
        else:
            finished.add(entry.id)

    def apply(current: StudioState) -> None:
        kept = []
        for entry in current.pending_cleanups:
            if entry.id in finished:
                continue
            if entry.id in failed:
                entry.attempts += 1
                entry.last_error = failed[entry.id]
            kept.append(entry)
        current.pending_cleanups = kept

    store.mutate(apply)
