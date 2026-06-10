import os
import re
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.paths import PROJECTS_DIR
from backend.app.db.models import Listing, Product, ProductStatus
from backend.app.db.store import store
from backend.app.services.sku import ensure_color_skus, ensure_product_sku
from backend.app.services.store_profiles import get_store_profile

router = APIRouter()


class ProductCreate(BaseModel):
    project_id: str
    name: str
    source_url: str | None = None
    tags: list[str] = []


class ProductUpdate(BaseModel):
    name: str | None = None
    status: ProductStatus | None = None
    listing: Listing | None = None
    tags: list[str] | None = None
    metadata: dict | None = None


def safe_folder_name(value: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", value).strip()
    return cleaned[:120] or "produto"


def product_folder(product: Product) -> Path:
    for asset in product.assets:
        asset_path = Path(asset.path)
        if asset_path.exists():
            return asset_path.parent
    return PROJECTS_DIR / product.project_id / safe_folder_name(product.name)


def open_folder(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def ensure_skus_for_state_products() -> list[Product]:
    state = store.load()
    changed = False
    for product in state.products:
        project = next((item for item in state.projects if item.id == product.project_id), None)
        store_profile = get_store_profile(project.store_profile_id if project else None)
        if not product.metadata.get("sku"):
            ensure_product_sku(product, state.products, project, store_profile)
            changed = True
        color_names = [asset.kind.replace("color_", "", 1) for asset in product.assets if asset.kind.startswith("color_")]
        color_skus = product.metadata.get("color_skus")
        if color_names and (not isinstance(color_skus, dict) or any(color_name not in color_skus for color_name in color_names)):
            ensure_color_skus(product, color_names)
            changed = True
    if changed:
        store.save(state)
    return state.products


@router.get("")
def list_products(project_id: str | None = None) -> list[Product]:
    products = ensure_skus_for_state_products()
    if project_id:
        products = [p for p in products if p.project_id == project_id]
    return sorted(products, key=lambda p: p.created_at, reverse=True)


@router.post("")
def create_product(payload: ProductCreate) -> Product:
    state = store.load()
    if not any(p.id == payload.project_id for p in state.projects):
        raise HTTPException(status_code=404, detail="Projeto nao encontrado")
    project = next((p for p in state.projects if p.id == payload.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    product = Product(**payload.model_dump())
    ensure_product_sku(product, state.products, project, store_profile)
    return store.upsert_product(product)


@router.patch("/{product_id}")
def update_product(product_id: str, payload: ProductUpdate) -> Product:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    if "name" in payload.model_fields_set and payload.name is not None:
        product.name = payload.name
    if "status" in payload.model_fields_set and payload.status is not None:
        product.status = payload.status
    if "listing" in payload.model_fields_set and payload.listing is not None:
        product.listing = payload.listing
    if "tags" in payload.model_fields_set and payload.tags is not None:
        product.tags = payload.tags
    if "metadata" in payload.model_fields_set and payload.metadata is not None:
        product.metadata.update(payload.metadata)

    return store.upsert_product(product)


@router.post("/{product_id}/open-folder")
def open_product_folder(product_id: str) -> dict[str, str]:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    folder = product_folder(product)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        open_folder(folder)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Nao foi possivel abrir a pasta: {exc}") from exc
    return {"status": "opened", "path": str(folder)}


@router.delete("/{product_id}")
def delete_product(product_id: str) -> dict[str, str]:
    state = store.load()
    if not any(product.id == product_id for product in state.products):
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    state.products = [product for product in state.products if product.id != product_id]
    state.jobs = [job for job in state.jobs if job.product_id != product_id]
    store.save(state)
    return {"status": "deleted", "product_id": product_id}
