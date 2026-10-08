import io
import re
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile
from pathlib import Path

import unicodedata

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from PIL import Image
from pydantic import BaseModel, Field

from backend.app.db.models import Asset, Listing, Product, ProductStatus, StudioState, now_iso
from backend.app.db.store import store
from backend.app.core.paths import CACHE_DIR
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
from backend.app.services.product_cleanup import queue_product_cleanup, run_pending_cleanups
from backend.app.services.product_health import cached_product_file_warnings
from backend.app.services.product_queries import (
    CHARACTERISTICS,
    PUBLICATIONS,
    catalog_stats,
    is_listed,
    page_products,
    product_matches,
)
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
from backend.app.services.authorization import current_store_id, store_project_ids
from backend.app.services.store_catalog import ensure_store_catalog
from backend.app.services.image_versions import replace_with_new_version

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


class VariationCreate(BaseModel):
    attribute: str
    value: str


def product_folder(product: Product) -> Path:
    return product_dir_for(product)


def ensure_skus_for_state_products() -> list[Product]:
    """Backfill missing SKUs. The returned products are read-only when nothing changed."""
    preview = store.snapshot()

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

    # Resolve profiles before entering JsonStore.mutate. Calling
    # get_store_profile() inside the mutation would try to acquire the same
    # non-reentrant store lock and could deadlock legacy products without SKU.
    profiles_by_id = {profile.id: profile for profile in preview.store_profiles}
    fallback_profile = preview.store_profiles[0] if preview.store_profiles else get_store_profile(None)

    def apply(state: StudioState) -> list[Product]:
        for product in state.products:
            project = next((item for item in state.projects if item.id == product.project_id), None)
            store_profile = profiles_by_id.get(project.store_profile_id if project else "") or fallback_profile
            if not product.metadata.get("sku"):
                ensure_product_sku(product, state.products, project, store_profile)
            color_names = [asset.kind.replace("color_", "", 1) for asset in product.assets if asset.kind.startswith("color_")]
            if color_names:
                ensure_color_skus(product, color_names)
        return state.products

    return store.mutate(apply)


# Prompts the AI used and the scraped description are stored for reference
# only; they make up most of the catalog payload and the list view never reads
# them. PATCH merges metadata, so omitting them here never erases them.
LIST_OMITTED_METADATA = {"image_prompts", "listing_prompt", "image_prompt", "color_variation_prompt", "description"}


def _public_product(product: Product, *, summary: bool = False) -> Product:
    # Shallow copy: the result is only serialized, so it may share nested
    # values with the cached store state as long as nothing here mutates them.
    metadata = {
        key: value
        for key, value in product.metadata.items()
        if key != "file_warnings" and not (summary and key in LIST_OMITTED_METADATA)
    }
    warnings = cached_product_file_warnings(product)
    if warnings:
        metadata["file_warnings"] = warnings
    assets = [asset.model_copy(update={"path": Path(asset.path).name}) for asset in product.assets]
    return product.model_copy(update={"metadata": metadata, "assets": assets})


@router.get("")
def list_products(request: Request) -> list[Product]:
    products = _store_products(request)
    return sorted((_public_product(p, summary=True) for p in products), key=lambda p: p.created_at, reverse=True)


def _store_products(request: Request) -> list[Product]:
    products = ensure_skus_for_state_products()
    allowed_projects = store_project_ids(store.snapshot(), current_store_id(request))
    return [product for product in products if product.project_id in allowed_projects]


@router.get("/page")
def list_products_page(
    request: Request,
    q: str = "",
    status: str = "all",
    characteristic: str = "all",
    publication: str = "all",
    limit: int = Query(40, ge=1, le=200),
    cursor: str | None = None,
) -> dict:
    """One page of the store catalog, newest first, filtered on the server."""
    if status != "all" and status not in {item.value for item in ProductStatus}:
        raise HTTPException(status_code=422, detail="Status inválido")
    if characteristic not in CHARACTERISTICS:
        raise HTTPException(status_code=422, detail="Característica inválida")
    if publication not in PUBLICATIONS:
        raise HTTPException(status_code=422, detail="Publicação inválida")
    products = _store_products(request)
    store_total = len(products)
    matched = [
        product
        for product in products
        if product_matches(product, query=q, status=status, characteristic=characteristic)
    ]
    # The publication tabs show both counts for the other filters, so the
    # split is counted before it is applied.
    listed_total = sum(1 for product in matched if is_listed(product))
    not_listed_total = len(matched) - listed_total
    if publication != "all":
        matched = [product for product in matched if is_listed(product) == (publication == "listed")]
    try:
        page, next_cursor = page_products(matched, limit=limit, cursor=cursor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "items": [_public_product(product, summary=True) for product in page],
        "next_cursor": next_cursor,
        "total": len(matched),
        "with_title": sum(1 for product in matched if product.listing.title),
        "store_total": store_total,
        "listed_total": listed_total,
        "not_listed_total": not_listed_total,
    }


@router.get("/stats")
def products_stats(request: Request) -> dict:
    return catalog_stats(_store_products(request))


@router.get("/{product_id}")
def get_product(product_id: str, request: Request) -> Product:
    product = next((item for item in _store_products(request) if item.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    return _public_product(product)


@router.post("")
def create_product(payload: ProductCreate, request: Request) -> Product:
    project = ensure_store_catalog(current_store_id(request))
    state = store.load()
    store_profile = get_store_profile(project.store_profile_id)
    product = Product(**payload.model_dump(), project_id=project.id)
    ensure_product_sku(product, state.products, project, store_profile)
    return _public_product(store.upsert_product(product))


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

    return _public_product(store.upsert_product(product))


def _production_context(product: Product):
    state = store.load()
    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    filaments = [item for item in state.filament_spools if item.store_profile_id == store_profile.id]
    settings = get_production_settings(state, store_profile.id)
    return filaments, settings


@router.put("/production-costs/batch")
def batch_update_production_costs(payload: ProductionCostBatchRequest, request: Request) -> dict:
    if not payload.items:
        return {"updated": 0, "product_ids": []}

    preview = store.load()
    allowed_projects = store_project_ids(preview, current_store_id(request))
    missing_ids = [
        item.product_id
        for item in payload.items
        if not next(
            (entry for entry in preview.products if entry.id == item.product_id and entry.project_id in allowed_projects),
            None,
        )
    ]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Produto(s) nao encontrado(s): {', '.join(dict.fromkeys(missing_ids))}",
        )

    def apply(state: StudioState) -> dict:
        updated_ids: list[str] = []
        for item in payload.items:
            product = next(
                (entry for entry in state.products if entry.id == item.product_id and entry.project_id in allowed_projects),
                None,
            )
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


@router.get("/{product_id}/download-files")
def download_product_files(product_id: str) -> FileResponse:
    state = store.load()
    product = next((p for p in state.products if p.id == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    folder = product_folder(product)
    # Dot-prefixed names are images still being generated.
    files = [
        path for path in folder.rglob("*")
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(folder).parts)
    ] if folder.exists() else []
    if not files:
        raise HTTPException(status_code=404, detail="Este produto ainda não possui arquivos locais")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(prefix=f"produto-{product.id}-", suffix=".zip", dir=CACHE_DIR, delete=False)
    temporary.close()
    archive_path = Path(temporary.name)
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(folder).as_posix())
    filename_base = slugify(str(product.metadata.get("sku") or product.name)) or product.id
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"{filename_base}-arquivos.zip",
        background=BackgroundTask(archive_path.unlink, missing_ok=True),
    )


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
    return _public_product(store.upsert_product(product))


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
    return _public_product(store.upsert_product(product))


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
    kind = f"generated_{prompt_key}"

    def save_upload(path: Path) -> None:
        with Image.open(io.BytesIO(content)) as image:
            image.convert("RGB").save(path, format="PNG")

    try:
        replace_with_new_version(product, kind, output_path, save_upload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Imagem invalida: {exc}") from exc

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
    return _public_product(store.upsert_product(product))


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
    return _public_product(store.upsert_product(product))


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
    return _public_product(store.upsert_product(product))


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
    return _public_product(store.upsert_product(product))


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
    return _public_product(store.upsert_product(product))


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

    return _public_product(store.upsert_product(product))


class DeleteProductsRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=2000)


def _remove_products(product_ids: set[str]) -> tuple[list[Product], list[dict]]:
    """Remove products, their jobs and schedule entries in one write.

    One write means one safety backup of the store for the whole batch. Their
    files are queued in the same write and removed after the response.
    """
    removed: list[Product] = []
    blocked_urls: list[dict] = []

    def apply(state: StudioState) -> None:
        for target in state.products:
            if target.id not in product_ids:
                continue
            removed.append(target.model_copy(deep=True))
            blocked = block_product_source_url(state, target)
            if blocked:
                blocked_urls.append(blocked.model_dump())
        state.products = [item for item in state.products if item.id not in product_ids]
        state.jobs = [job for job in state.jobs if job.product_id not in product_ids]
        state.print_schedule_tasks = [
            task for task in state.print_schedule_tasks if task.product_id not in product_ids
        ]
        queue_product_cleanup(state, removed)

    if product_ids:
        store.mutate(apply, allow_product_shrink=True)
    return removed, blocked_urls


@router.post("/delete-batch")
def delete_products(payload: DeleteProductsRequest, request: Request, background: BackgroundTasks) -> dict:
    state = store.snapshot()
    allowed = store_project_ids(state, current_store_id(request))
    requested = set(payload.product_ids)
    # Products of other stores are treated as already gone.
    owned = {product.id for product in state.products if product.id in requested and product.project_id in allowed}
    removed, blocked_urls = _remove_products(owned)
    background.add_task(run_pending_cleanups)
    return {
        "status": "deleted",
        "product_ids": [product.id for product in removed],
        "blocked_urls": blocked_urls,
    }


@router.delete("/{product_id}")
def delete_product(product_id: str, background: BackgroundTasks) -> dict:
    removed, blocked_urls = _remove_products({product_id})
    if not removed:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    background.add_task(run_pending_cleanups)
    return {
        "status": "deleted",
        "product_id": product_id,
        "blocked_url": blocked_urls[0] if blocked_urls else None,
    }
