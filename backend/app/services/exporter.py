import csv
import re
from datetime import datetime
from pathlib import Path

from backend.app.core.paths import EXPORTS_DIR
from backend.app.db.models import Asset, Marketplace, Product, ProductStatus
from backend.app.db.store import store
from backend.app.services.cloudflare_r2 import r2_configured, upload_file_to_r2
from backend.app.services.image_generation import r2_key_prefix
from backend.app.services.sku import ensure_color_skus, ensure_product_sku
from backend.app.services.store_profiles import get_store_profile

# Cabecalho completo da planilha validada da Shopee (importacao com variantes).
SHOPEE_HEADERS = [
    "Categoria",
    "Nome do Produto",
    "Descrição do Produto",
    "SKU principal",
    "Número de Integração de Variação",
    "Nome da Variação 1",
    "Opção para Variação 1",
    "Imagem por Variação",
    "Nome da Variação 2",
    "Opção para Variação 2",
    "Preço",
    "Estoque",
    "SKU da Variação",
    "Template da Tabela de Medidas",
    "Imagem de Tamanhos",
    "GTIN (EAN)",
    "IDs de compatibilidade",
    "Imagem de capa",
    "Imagem do produto 1",
    "Imagem do produto 2",
    "Imagem do produto 3",
    "Imagem do produto 4",
    "Imagem do produto 5",
    "Imagem do produto 6",
    "Imagem do produto 7",
    "Imagem do produto 8",
    "Peso",
    "Comprimento",
    "Largura",
    "Altura",
    "Retirada pelo Comprador",
    "Shopee Xpress",
    "Prazo de Postagem para Encomenda",
    "NCM",
    "CFOP (Mesmo Estado)",
    "CFOP (Outro Estado)",
    "Origem",
    "CSOSN",
    "CEST",
    "Unidade de Medida",
    "CST PIS/Cofins",
    "% total de tributos federais, estaduais e municipais",
    "Tipo de Operação",
    "EX TIPI (tabela de exceções IPI)",
    "Nr. de controle da FCI",
    "Nr. RECOPI",
    "Informações adicionais do produto",
    "Produto é um item agrupável",
    "GTIN da Unidade Tributável",
    "Quantidade da Unidade Tributável",
    "Unidade de medida do item agrupável",
    "Motivo da Falha",
]

VARIATION_NAME = "Cor"

# Nomes de exibicao (PT-BR) para as opcoes de variacao de cor.
COLOR_DISPLAY_NAMES = {
    "PLA_Yellow": "Amarelo",
    "PLA_Black": "Preto",
    "PLA_GreyMetallic": "Cinza Metálico",
    "PLA_TiffanyBlue": "Azul Tiffany",
    "PLA_Red": "Vermelho",
    "PLA_Green": "Verde",
    "PLA_BlueMetallic": "Azul Metálico",
    "PLA_Blue": "Azul",
    "PLA_Purple": "Roxo",
    "PLA_BabyPink": "Rosa Bebê",
    "PLA_NeonPink": "Rosa Neon",
    "PLA_BabyBlue": "Azul Bebê",
    "PLA_Magenta": "Magenta",
    "Velvet_White": "Branco Veludo",
}

_MATERIAL_PREFIXES = ("PLA_", "PETG_", "ABS_", "TPU_")


def color_display_name(color_id: str) -> str:
    if color_id in COLOR_DISPLAY_NAMES:
        return COLOR_DISPLAY_NAMES[color_id]
    text = color_id
    for prefix in _MATERIAL_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.replace("_", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return text.strip().title() or color_id


def is_image_asset(asset: Asset) -> bool:
    return asset.kind == "cover_image" or asset.kind.startswith("generated_") or asset.kind.startswith("color_")


def _ensure_public_url(product: Product, asset: Asset) -> str | None:
    if not asset.public_url and r2_configured():
        asset.public_url = upload_file_to_r2(asset.path, r2_key_prefix(product))
    return asset.public_url


def gallery_image_urls(product: Product) -> list[str]:
    """Imagens principais do produto (capa + imagens base), sem as variacoes de cor."""
    cover_urls: list[str] = []
    other_urls: list[str] = []
    for asset in product.assets:
        if asset.kind == "cover_image":
            url = _ensure_public_url(product, asset)
            if url:
                cover_urls.append(url)
        elif asset.kind.startswith("generated_"):
            url = _ensure_public_url(product, asset)
            if url:
                other_urls.append(url)
    return (cover_urls + other_urls)[:9]


def color_image_map(product: Product) -> dict[str, str]:
    """Mapeia o id da cor para a URL publica da imagem da variacao."""
    result: dict[str, str] = {}
    for asset in product.assets:
        if not asset.kind.startswith("color_"):
            continue
        color_id = asset.kind[len("color_") :]
        if not color_id or color_id in result:
            continue
        url = _ensure_public_url(product, asset)
        if url:
            result[color_id] = url
    return result


def ordered_variation_colors(product: Product, color_urls: dict[str, str]) -> list[str]:
    """Ordena as cores: primeiro as definidas em color_skus, depois as que so tem imagem."""
    color_skus = product.metadata.get("color_skus")
    ordered: list[str] = []
    if isinstance(color_skus, dict):
        ordered.extend(color_skus.keys())
    for color_id in color_urls:
        if color_id not in ordered:
            ordered.append(color_id)
    return ordered


def ensure_public_image_urls(product: Product) -> list[str]:
    """Compatibilidade: todas as imagens (capa, base e cores)."""
    urls = gallery_image_urls(product)
    for url in color_image_map(product).values():
        if url not in urls:
            urls.append(url)
    return urls[:9]


def _base_row(product: Product, gallery: list[str]) -> dict[str, str]:
    row = {header: "" for header in SHOPEE_HEADERS}
    row["Categoria"] = product.listing.category
    row["Nome do Produto"] = product.listing.title
    row["Descrição do Produto"] = product.listing.description
    row["SKU principal"] = product.metadata.get("sku") or ""
    row["Preço"] = (product.listing.price or "").replace(".", ",")
    row["Estoque"] = str(product.listing.stock)
    row["Peso"] = product.listing.weight
    row["Comprimento"] = "10"
    row["Largura"] = "10"
    row["Altura"] = "10"
    if gallery:
        row["Imagem de capa"] = gallery[0]
    for index, url in enumerate(gallery[1:9], start=1):
        row[f"Imagem do produto {index}"] = url
    return row


def build_product_rows(product: Product) -> list[dict[str, str]]:
    gallery = gallery_image_urls(product)
    color_urls = color_image_map(product)
    colors = ordered_variation_colors(product, color_urls)

    if not colors:
        return [_base_row(product, gallery)]

    color_skus = ensure_color_skus(product, colors)
    rows: list[dict[str, str]] = []
    for index, color_id in enumerate(colors, start=1):
        row = _base_row(product, gallery)
        row["Número de Integração de Variação"] = str(index)
        row["Nome da Variação 1"] = VARIATION_NAME
        row["Opção para Variação 1"] = color_display_name(color_id)
        row["Imagem por Variação"] = color_urls.get(color_id, "")
        row["SKU da Variação"] = color_skus.get(color_id, "")
        rows.append(row)
    return rows


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
            for row in build_product_rows(product):
                writer.writerow(row)

            product.status = ProductStatus.exported
            store.upsert_product(product)

    return {"path": str(output), "count": len(ready), "marketplace": marketplace.value}
