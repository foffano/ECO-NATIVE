import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.core.paths import DATA_DIR
from backend.app.db.models import Marketplace
from backend.app.services.exporter import export_shopee_template
from backend.app.services.public_images import PublicUrlMissing
from backend.app.db.store import store
from backend.app.services.authorization import current_store_id, store_project_ids
from backend.app.services.shopee_template import ShopeeTemplateError, validate_template

router = APIRouter()

STORE_TEMPLATES_DIR = DATA_DIR / "store_templates"
MAX_TEMPLATE_BYTES = 10 * 1024 * 1024
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExportRequest(BaseModel):
    marketplace: Marketplace = Marketplace.shopee
    product_ids: list[str] = []


def shopee_template_path(store_id: str) -> Path:
    return STORE_TEMPLATES_DIR / store_id / "shopee_mass_upload.xlsx"


def _store_product_ids(payload: ExportRequest, store_id: str) -> list[str]:
    """The requested products of this store; none requested means the whole catalog."""
    state = store.snapshot()
    allowed_projects = store_project_ids(state, store_id)
    allowed = [product.id for product in state.products if product.project_id in allowed_projects]
    if not payload.product_ids:
        product_ids = allowed
    else:
        allowed_set = set(allowed)
        product_ids = [product_id for product_id in payload.product_ids if product_id in allowed_set]
    if not product_ids:
        raise HTTPException(status_code=400, detail="Nenhum produto valido para exportar")
    return product_ids


def _export_headers(result: dict) -> dict[str, str]:
    return {
        "X-Eco-Export-Count": str(result["count"]),
        "X-Eco-Export-Marketplace": str(result["marketplace"]),
    }


@router.get("/shopee-template")
def shopee_template_status(request: Request) -> dict:
    path = shopee_template_path(current_store_id(request))
    if not path.is_file():
        return {"configured": False}
    uploaded_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return {"configured": True, "uploaded_at": uploaded_at}


@router.post("/shopee-template")
async def upload_shopee_template(request: Request, file: UploadFile = File(...)) -> dict:
    """Keep the store's own template from the Shopee Seller Centre."""
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Envie o template .xlsx baixado da Shopee")
    content = await file.read(MAX_TEMPLATE_BYTES + 1)
    if len(content) > MAX_TEMPLATE_BYTES:
        raise HTTPException(status_code=400, detail="Template maior que 10 MB")
    destination = shopee_template_path(current_store_id(request))
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".template-", suffix=".xlsx", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        validate_template(Path(temporary))
        os.replace(temporary, destination)
    except ShopeeTemplateError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        Path(temporary).unlink(missing_ok=True)
    return shopee_template_status(request)


@router.post("/shopee-xlsx")
def create_shopee_xlsx(payload: ExportRequest, request: Request) -> FileResponse:
    store_id = current_store_id(request)
    product_ids = _store_product_ids(payload, store_id)
    template = shopee_template_path(store_id)
    if not template.is_file():
        raise HTTPException(status_code=409, detail="Envie primeiro o template de envio em massa baixado da Shopee")
    try:
        result = export_shopee_template(template, "", product_ids)
    except (ShopeeTemplateError, PublicUrlMissing) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not result:
        raise HTTPException(status_code=400, detail="Nenhum produto valido para exportar")
    path = Path(str(result["path"]))
    return FileResponse(path, media_type=XLSX_MEDIA_TYPE, filename=path.name, headers=_export_headers(result))
