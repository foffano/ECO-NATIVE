from __future__ import annotations

import re
from pathlib import Path

from backend.app.core.paths import PROJECTS_DIR
from backend.app.db.models import Product, Project, StoreProfile
from backend.app.services.sku import generate_product_sku


def safe_sku_folder(sku: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", sku.strip()).strip()
    return cleaned[:120] or "SEM-SKU"


def product_assets_dir(project_id: str, sku: str) -> Path:
    return PROJECTS_DIR / project_id / safe_sku_folder(sku)


def product_dir_for(product: Product) -> Path:
    sku = str(product.metadata.get("sku") or "").strip()
    if sku:
        return product_assets_dir(product.project_id, sku)
    for asset in product.assets:
        asset_path = Path(asset.path)
        if asset_path.exists():
            return asset_path.parent
    return PROJECTS_DIR / product.project_id / safe_sku_folder(sku or "produto")


def cover_image_filename(sku: str) -> str:
    return f"{sku}_capa_produto.jpg"


def model_filename(sku: str, suffix: str = ".3mf") -> str:
    return f"{sku}_model{suffix}"


def extra_model_filename(sku: str, index: int, suffix: str = ".3mf") -> str:
    return f"{sku}_model_extra_{index}{suffix}"


def is_model_asset_kind(kind: str) -> bool:
    return kind == "model_3mf" or kind.startswith("model_3mf_extra")


MODEL_FILE_SUFFIXES = {".3mf", ".stl"}


def studio_image_filename(sku: str, prompt_key: str) -> str:
    return f"{sku}_capa_produto_{prompt_key}.png"


def color_variation_filename(sku: str, source_prompt_key: str, color_name: str) -> str:
    return f"{sku}_capa_produto_{source_prompt_key}_{color_name}.png"


def resolve_sku_for_capture(
    product_name: str,
    sku_reference_products: list[Product],
    project: Project | None,
    store_profile: StoreProfile,
) -> str:
    return generate_product_sku(product_name, sku_reference_products, project, store_profile)
