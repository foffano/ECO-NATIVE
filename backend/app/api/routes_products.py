import io
import os
import re
import subprocess
import sys
from pathlib import Path

import unicodedata

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel

from backend.app.db.models import Asset, Listing, PrintPlate, Product, ProductStatus, StudioState, now_iso
from backend.app.db.store import store
from backend.app.services.cover_image import CoverImageError, cover_r2_public_url, normalize_cover_to_jpeg, validate_cover_bytes
from backend.app.services.cloudflare_r2 import r2_configured, upload_file_to_r2
from backend.app.services.product_paths import (
    MODEL_FILE_SUFFIXES,
    cover_image_filename,
    extra_model_filename,
    is_model_asset_kind,
    manual_color_filename,
    model_filename,
    product_dir_for,
    studio_image_filename,
    variation_image_filename,
)
from backend.app.services.prompt_library import IMAGE_PROMPTS
from backend.app.services.print_plates import plate_totals, read_print_plates, write_print_plates
from backend.app.services.product_cleanup import purge_product_data
from backend.app.services.product_health import product_file_warnings
from backend.app.services.production_cost import (
    ProductionCost,
    build_production_cost_breakdown,
    get_production_settings,
    normalize_production_cost,
    write_production_cost,
)
from backend.app.services.source_url_blacklist import block_product_source_url
from backend.app.services.sku import ensure_color_skus, ensure_product_sku, variation_sku
from backend.app.services.store_profiles import get_store_profile

router = APIRouter()

MAX_MODEL_FILE_BYTES = 50 * 1024 * 1024
MAX_COVER_IMAGE_BYTES = 15 * 1024 * 1024
COVER_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    return slug


def _unique_slug(base: str, taken: set[str]) -> str:
    base = base or "item"
    slug = base
    index = 2
    while slug in taken:
        slug = f"{base}_{index}"
        index += 1
    return slug


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


class ProductionCostBatchItem(BaseModel):
    product_id: str
    production_cost: ProductionCost


class ProductionCostBatchRequest(BaseModel):
    items: list[ProductionCostBatchItem]


class PrintPlatesUpdate(BaseModel):
    plates: list[PrintPlate]


class VariationCreate(BaseModel):
    attribute: str
    value: str


def product_folder(product: Product) -> Path:
    return product_dir_for(product)


def open_folder(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def ensure_skus_for_state_products() -> list[Product]:
    preview = store.load()

    def needs_sku_updates(state: StudioState) -> bool:
        for product in state.products:
            if not product.metadata.get("sku"):
                return True
            color_names = [asset.kind.replace("color_", "", 1) for asset in product.assets if asset.kind.startswith("color_")]
            color_skus = product.metadata.get("color_skus")
            if color_names and (not isinstance(color_skus, dict) or any(color_name not in color_skus for color_name in color_names)):
                return True
        return False

    if not needs_sku_updates(preview):
        return preview.products

    def apply(state: StudioState) -> list[Product]:
        for product in state.products:
            project = next((item for item in state.projects if item.id == product.project_id), None)
            store_profile = get_store_profile(project.store_profile_id if project else None)
            if not product.metadata.get("sku"):
                ensure_product_sku(product, state.products, project, store_profile)
            color_names = [asset.kind.replace("color_", "", 1) for asset in product.assets if asset.kind.startswith("color_")]
            if color_names:
                ensure_color_skus(product, color_names)
        return state.products

    return store.mutate(apply)


def _annotate_product_health(product: Product) -> Product:
    warnings = product_file_warnings(product)
    if warnings:
        product.metadata["file_warnings"] = warnings
    else:
        product.metadata.pop("file_warnings", None)
    return product


@router.get("")
def list_products(project_id: str | None = None) -> list[Product]:
    products = ensure_skus_for_state_products()
    if project_id:
        products = [p for p in products if p.project_id == project_id]
    return sorted((_annotate_product_health(p.model_copy(deep=True)) for p in products), key=lambda p: p.created_at, reverse=True)


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


def _production_context(product: Product):
    state = store.load()
    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    filaments = [item for item in state.filament_spools if item.store_profile_id == store_profile.id]
    settings = get_production_settings(state, store_profile.id)
    return filaments, settings


@router.put("/production-costs/batch")
def batch_update_production_costs(payload: ProductionCostBatchRequest) -> dict:
    if not payload.items:
        return {"updated": 0, "product_ids": []}

    preview = store.load()
    missing_ids = [
        item.product_id
        for item in payload.items
        if not next((entry for entry in preview.products if entry.id == item.product_id), None)
    ]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Produto(s) nao encontrado(s): {', '.join(dict.fromkeys(missing_ids))}",
        )

    def apply(state: StudioState) -> dict:
        updated_ids: list[str] = []
        for item in payload.items:
            product = next((entry for entry in state.products if entry.id == item.product_id), None)
            if not product:
                continue
            write_production_cost(product, normalize_production_cost(item.production_cost))
            product.updated_at = now_iso()
            updated_ids.append(product.id)
        return {"updated": len(updated_ids), "product_ids": updated_ids}

    return store.mutate(apply)


@router.get("/{product_id}/production-cost")
def get_production_cost(product_id: str) -> dict:
    state = store.load()
    product = next((item for item in state.products if item.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    filaments, settings = _production_context(product)
    breakdown = build_production_cost_breakdown(product, filaments, settings)
    return breakdown.model_dump()


@router.put("/{product_id}/production-cost")
def update_production_cost(product_id: str, payload: ProductionCost) -> dict:
    state = store.load()
    product = next((item for item in state.products if item.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    write_production_cost(product, normalize_production_cost(payload))
    store.upsert_product(product)
    filaments, settings = _production_context(product)
    breakdown = build_production_cost_breakdown(product, filaments, settings)
    return breakdown.model_dump()


@router.get("/{product_id}/print-plates")
def get_print_plates(product_id: str) -> dict:
    state = store.load()
    product = next((item for item in state.products if item.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    plates = read_print_plates(product)
    return {"plates": [plate.model_dump() for plate in plates], "totals": plate_totals(plates)}


@router.put("/{product_id}/print-plates")
def update_print_plates(product_id: str, payload: PrintPlatesUpdate) -> dict:
    state = store.load()
    product = next((item for item in state.products if item.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    plates = payload.plates
    write_print_plates(product, plates)
    store.upsert_product(product)
    return {"plates": [plate.model_dump() for plate in plates], "totals": plate_totals(plates)}


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


def _next_extra_model_index(product: Product) -> int:
    indices = []
    for asset in product.assets:
        if asset.kind == "model_3mf":
            continue
        match = re.fullmatch(r"model_3mf_extra_(\d+)", asset.kind)
        if match:
            indices.append(int(match.group(1)))
    return max(indices, default=0) + 1


@router.post("/{product_id}/model-files")
async def upload_model_file(product_id: str, file: UploadFile = File(...)) -> Product:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    original_name = Path(file.filename or "modelo.3mf").name
    suffix = Path(original_name).suffix.lower() or ".3mf"
    if suffix not in MODEL_FILE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Formato nao suportado. Use arquivos .3mf ou .stl.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > MAX_MODEL_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo maior que 50MB.")

    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    ensure_product_sku(product, state.products, project, store_profile)
    sku = str(product.metadata.get("sku") or "").strip()
    if not sku:
        raise HTTPException(status_code=400, detail="SKU do produto nao encontrado.")

    folder = product_folder(product)
    folder.mkdir(parents=True, exist_ok=True)

    has_primary = any(asset.kind == "model_3mf" for asset in product.assets)
    if not has_primary:
        output_name = model_filename(sku, suffix)
        kind = "model_3mf"
    else:
        index = _next_extra_model_index(product)
        output_name = extra_model_filename(sku, index, suffix)
        kind = f"model_3mf_extra_{index}"

    output_path = folder / output_name
    output_path.write_bytes(content)

    product.assets.append(
        Asset(
            product_id=product.id,
            kind=kind,
            path=str(output_path),
        )
    )
    if product.metadata.get("model_download_error"):
        product.metadata.pop("model_download_error", None)
    return store.upsert_product(product)


@router.post("/{product_id}/cover-image")
async def upload_cover_image(product_id: str, file: UploadFile = File(...)) -> Product:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    original_name = Path(file.filename or "capa.jpg").name
    suffix = Path(original_name).suffix.lower() or ".jpg"
    if suffix not in COVER_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Formato nao suportado. Use arquivos JPG, PNG ou WEBP.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > MAX_COVER_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que 15MB.")

    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    ensure_product_sku(product, state.products, project, store_profile)
    sku = str(product.metadata.get("sku") or "").strip()
    if not sku:
        raise HTTPException(status_code=400, detail="SKU do produto nao encontrado.")

    folder = product_folder(product)
    folder.mkdir(parents=True, exist_ok=True)
    output_path = folder / cover_image_filename(sku)
    output_path.write_bytes(content)

    try:
        validate_cover_bytes(output_path.read_bytes(), output_path)
        normalize_cover_to_jpeg(output_path)
        validate_cover_bytes(output_path.read_bytes(), output_path)
    except CoverImageError as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cover = next((asset for asset in product.assets if asset.kind == "cover_image"), None)
    if cover:
        cover.path = str(output_path)
    else:
        cover = Asset(product_id=product.id, kind="cover_image", path=str(output_path))
        product.assets.append(cover)

    if r2_configured():
        try:
            cover.public_url = cover_r2_public_url(product, cover)
        except CoverImageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    product.updated_at = now_iso()
    return store.upsert_product(product)


@router.post("/{product_id}/style-image/{prompt_key}")
async def upload_style_image(product_id: str, prompt_key: str, file: UploadFile = File(...)) -> Product:
    if prompt_key not in IMAGE_PROMPTS:
        raise HTTPException(status_code=400, detail="Estilo de imagem desconhecido.")

    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    original_name = Path(file.filename or "imagem.png").name
    suffix = Path(original_name).suffix.lower() or ".png"
    if suffix not in COVER_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Formato nao suportado. Use arquivos JPG, PNG ou WEBP.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > MAX_COVER_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que 15MB.")

    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    ensure_product_sku(product, state.products, project, store_profile)
    sku = str(product.metadata.get("sku") or "").strip()
    if not sku:
        raise HTTPException(status_code=400, detail="SKU do produto nao encontrado.")

    folder = product_folder(product)
    folder.mkdir(parents=True, exist_ok=True)
    output_path = folder / studio_image_filename(sku, prompt_key)

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.convert("RGB").save(output_path, format="PNG")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Imagem invalida: {exc}") from exc

    kind = f"generated_{prompt_key}"
    asset = next((item for item in product.assets if item.kind == kind), None)
    if asset:
        asset.path = str(output_path)
        asset.public_url = None
    else:
        asset = Asset(product_id=product.id, kind=kind, path=str(output_path))
        product.assets.append(asset)

    if r2_configured():
        try:
            asset.public_url = upload_file_to_r2(
                str(output_path),
                f"eco-native/{product.project_id}/{product.id}",
                force=True,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao publicar imagem no R2: {exc}") from exc

    product.updated_at = now_iso()
    return store.upsert_product(product)


def _require_product_sku(state: StudioState, product: Product) -> str:
    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    ensure_product_sku(product, state.products, project, store_profile)
    sku = str(product.metadata.get("sku") or "").strip()
    if not sku:
        raise HTTPException(status_code=400, detail="SKU do produto nao encontrado.")
    return sku


def _save_upload_as_png(content: bytes, output_path: Path) -> None:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.convert("RGB").save(output_path, format="PNG")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Imagem invalida: {exc}") from exc


def _validate_image_suffix(file: UploadFile) -> None:
    original_name = Path(file.filename or "imagem.png").name
    suffix = Path(original_name).suffix.lower() or ".png"
    if suffix not in COVER_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Formato nao suportado. Use arquivos JPG, PNG ou WEBP.")


@router.post("/{product_id}/color-image")
async def upload_manual_color_image(
    product_id: str,
    name: str = Form(...),
    file: UploadFile = File(...),
) -> Product:
    color_name = name.strip()
    if not color_name:
        raise HTTPException(status_code=400, detail="Informe o nome da cor.")

    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    _validate_image_suffix(file)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > MAX_COVER_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que 15MB.")

    sku = _require_product_sku(state, product)

    existing_slugs = {
        asset.kind.replace("color_", "", 1)
        for asset in product.assets
        if asset.kind.startswith("color_")
    }
    slug = slugify(color_name) or "cor"
    if slug not in existing_slugs:
        slug = _unique_slug(slug, existing_slugs)

    folder = product_folder(product)
    folder.mkdir(parents=True, exist_ok=True)
    output_path = folder / manual_color_filename(sku, slug)
    _save_upload_as_png(content, output_path)

    kind = f"color_{slug}"
    asset = next((item for item in product.assets if item.kind == kind), None)
    if asset:
        asset.path = str(output_path)
        asset.public_url = None
    else:
        asset = Asset(product_id=product.id, kind=kind, path=str(output_path))
        product.assets.append(asset)

    ensure_color_skus(product, [slug])
    labels = product.metadata.get("color_labels")
    labels = dict(labels) if isinstance(labels, dict) else {}
    labels[slug] = color_name
    product.metadata["color_labels"] = labels

    if r2_configured():
        try:
            asset.public_url = upload_file_to_r2(
                str(output_path),
                f"eco-native/{product.project_id}/{product.id}",
                force=True,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao publicar imagem no R2: {exc}") from exc

    product.updated_at = now_iso()
    return store.upsert_product(product)


def _manual_variations(product: Product) -> list[dict]:
    value = product.metadata.get("manual_variations")
    return list(value) if isinstance(value, list) else []


@router.post("/{product_id}/variations")
def create_variation(product_id: str, payload: VariationCreate) -> Product:
    attribute = payload.attribute.strip()
    value = payload.value.strip()
    if not attribute:
        raise HTTPException(status_code=400, detail="Informe o tipo da variacao (ex.: Tamanho).")
    if not value:
        raise HTTPException(status_code=400, detail="Informe o valor da variacao (ex.: G).")

    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    sku = _require_product_sku(state, product)

    variations = _manual_variations(product)
    taken = {str(entry.get("id")) for entry in variations if entry.get("id")}
    slug = _unique_slug(slugify(f"{attribute}_{value}") or "variacao", taken)

    entry = {
        "id": slug,
        "attribute": attribute,
        "value": value,
        "sku": variation_sku(sku, attribute, value),
    }
    variations.append(entry)
    product.metadata["manual_variations"] = variations
    product.updated_at = now_iso()
    return store.upsert_product(product)


@router.post("/{product_id}/variations/{slug}/image")
async def upload_variation_image(product_id: str, slug: str, file: UploadFile = File(...)) -> Product:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    variations = _manual_variations(product)
    if not any(str(entry.get("id")) == slug for entry in variations):
        raise HTTPException(status_code=404, detail="Variacao nao encontrada.")

    _validate_image_suffix(file)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > MAX_COVER_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Imagem maior que 15MB.")

    sku = _require_product_sku(state, product)
    folder = product_folder(product)
    folder.mkdir(parents=True, exist_ok=True)
    output_path = folder / variation_image_filename(sku, slug)
    _save_upload_as_png(content, output_path)

    kind = f"variation_{slug}"
    asset = next((item for item in product.assets if item.kind == kind), None)
    if asset:
        asset.path = str(output_path)
        asset.public_url = None
    else:
        asset = Asset(product_id=product.id, kind=kind, path=str(output_path))
        product.assets.append(asset)

    if r2_configured():
        try:
            asset.public_url = upload_file_to_r2(
                str(output_path),
                f"eco-native/{product.project_id}/{product.id}",
                force=True,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao publicar imagem no R2: {exc}") from exc

    product.updated_at = now_iso()
    return store.upsert_product(product)


@router.delete("/{product_id}/variations/{slug}")
def delete_variation(product_id: str, slug: str) -> Product:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    variations = _manual_variations(product)
    if not any(str(entry.get("id")) == slug for entry in variations):
        raise HTTPException(status_code=404, detail="Variacao nao encontrada.")

    kind = f"variation_{slug}"
    for asset in [item for item in product.assets if item.kind == kind]:
        asset_path = Path(asset.path)
        if asset_path.exists() and asset_path.is_file():
            asset_path.unlink(missing_ok=True)
    product.assets = [item for item in product.assets if item.kind != kind]
    product.metadata["manual_variations"] = [
        entry for entry in variations if str(entry.get("id")) != slug
    ]
    product.updated_at = now_iso()
    return store.upsert_product(product)


@router.delete("/{product_id}/assets/{asset_id}")
def delete_product_asset(product_id: str, asset_id: str) -> Product:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    asset = next((item for item in product.assets if item.id == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
    is_color = asset.kind.startswith("color_")
    if not is_model_asset_kind(asset.kind) and not is_color:
        raise HTTPException(status_code=400, detail="Somente arquivos 3D ou variacoes de cor podem ser removidos por aqui.")

    asset_path = Path(asset.path)
    if asset_path.exists() and asset_path.is_file():
        asset_path.unlink(missing_ok=True)

    product.assets = [item for item in product.assets if item.id != asset_id]

    if is_color:
        slug = asset.kind.replace("color_", "", 1)
        color_skus = product.metadata.get("color_skus")
        if isinstance(color_skus, dict) and slug in color_skus:
            color_skus = dict(color_skus)
            color_skus.pop(slug, None)
            product.metadata["color_skus"] = color_skus
        color_labels = product.metadata.get("color_labels")
        if isinstance(color_labels, dict) and slug in color_labels:
            color_labels = dict(color_labels)
            color_labels.pop(slug, None)
            product.metadata["color_labels"] = color_labels
        product.updated_at = now_iso()

    return store.upsert_product(product)


@router.delete("/{product_id}")
def delete_product(product_id: str) -> dict:
    removed_product: Product | None = None
    blocked_url: dict | None = None

    def apply(state: StudioState) -> None:
        nonlocal removed_product, blocked_url
        target = next((item for item in state.products if item.id == product_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Produto nao encontrado")
        removed_product = target.model_copy(deep=True)
        blocked = block_product_source_url(state, target)
        blocked_url = blocked.model_dump() if blocked else None
        state.products = [item for item in state.products if item.id != product_id]
        state.jobs = [job for job in state.jobs if job.product_id != product_id]
        state.print_schedule_tasks = [
            task for task in state.print_schedule_tasks if task.product_id != product_id
        ]

    store.mutate(apply, allow_product_shrink=True)

    cleanup: dict = {"local": None, "r2": None, "errors": []}
    if removed_product:
        try:
            cleanup = purge_product_data(removed_product)
        except Exception as exc:
            cleanup["errors"].append(str(exc))

    return {
        "status": "deleted",
        "product_id": product_id,
        "cleanup": cleanup,
        "blocked_url": blocked_url,
    }
