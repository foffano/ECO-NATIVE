import csv
from datetime import datetime
from pathlib import Path

from backend.app.core.paths import EXPORTS_DIR
from backend.app.db.models import Marketplace, ProductStatus
from backend.app.db.store import store
from backend.app.services.cloudflare_r2 import r2_configured, upload_file_to_r2
from backend.app.services.image_generation import r2_key_prefix
from backend.app.services.sku import ensure_product_sku
from backend.app.services.store_profiles import get_store_profile

SHOPEE_HEADERS = [
    "Categoria",
    "SKU",
    "SKUs das variacoes",
    "Nome do Produto",
    "Descricao do Produto",
    "Preco",
    "Estoque",
    "Peso",
    "Comprimento",
    "Largura",
    "Altura",
    "Imagem de capa",
    "Imagem do produto 1",
    "Imagem do produto 2",
    "Imagem do produto 3",
    "Imagem do produto 4",
    "Imagem do produto 5",
    "Imagem do produto 6",
    "Imagem do produto 7",
    "Imagem do produto 8",
]


def is_image_asset(asset) -> bool:
    return asset.kind == "cover_image" or asset.kind.startswith("generated_") or asset.kind.startswith("color_")


def ensure_public_image_urls(product) -> list[str]:
    urls: list[str] = []
    for asset in product.assets:
        if not is_image_asset(asset):
            continue
        if not asset.public_url and r2_configured():
            asset.public_url = upload_file_to_r2(asset.path, r2_key_prefix(product))
        if asset.public_url:
            urls.append(asset.public_url)
    return urls[:9]


def export_marketplace_csv(
    project_id: str,
    marketplace: Marketplace,
    product_ids: list[str],
) -> dict[str, str | int] | None:
    state = store.load()
    if product_ids:
        selected_ids = set(product_ids)
        products = [p for p in state.products if p.id in selected_ids]
    else:
        products = [p for p in state.products if p.project_id == project_id]

    ready = [p for p in products if p.listing.title and p.listing.description]
    if not ready:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(EXPORTS_DIR) / f"{marketplace.value}_export_{timestamp}.csv"

    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHOPEE_HEADERS, delimiter=";")
        writer.writeheader()
        for product in ready:
            project = next((item for item in state.projects if item.id == product.project_id), None)
            store_profile = get_store_profile(project.store_profile_id if project else None)
            ensure_product_sku(product, state.products, project, store_profile)
            image_urls = ensure_public_image_urls(product)
            row = {header: "" for header in SHOPEE_HEADERS}
            row["Categoria"] = product.listing.category
            row["SKU"] = product.metadata.get("sku") or ""
            color_skus = product.metadata.get("color_skus")
            if isinstance(color_skus, dict):
                row["SKUs das variacoes"] = " | ".join(f"{key}:{value}" for key, value in sorted(color_skus.items()))
            row["Nome do Produto"] = product.listing.title
            row["Descricao do Produto"] = product.listing.description
            row["Preco"] = product.listing.price.replace(".", ",")
            row["Estoque"] = product.listing.stock
            row["Peso"] = product.listing.weight
            row["Comprimento"] = "10"
            row["Largura"] = "10"
            row["Altura"] = "10"
            if image_urls:
                row["Imagem de capa"] = image_urls[0]
            for index, url in enumerate(image_urls[1:9], start=1):
                row[f"Imagem do produto {index}"] = url
            writer.writerow(row)

            product.status = ProductStatus.exported
            store.upsert_product(product)

    return {"path": str(output), "count": len(ready), "marketplace": marketplace.value}
