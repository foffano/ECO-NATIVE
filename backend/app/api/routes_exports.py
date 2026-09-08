from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.db.models import Marketplace
from backend.app.services.exporter import export_marketplace_csv
from backend.app.db.store import store
from backend.app.services.authorization import current_store_id, require_project

router = APIRouter()


class ExportRequest(BaseModel):
    project_id: str
    marketplace: Marketplace = Marketplace.shopee
    product_ids: list[str] = []


@router.post("")
def create_export(payload: ExportRequest, request: Request) -> FileResponse:
    require_project(store.load(), payload.project_id, current_store_id(request))
    result = export_marketplace_csv(
        project_id=payload.project_id,
        marketplace=payload.marketplace,
        product_ids=payload.product_ids,
    )
    if not result:
        raise HTTPException(status_code=400, detail="Nenhum produto valido para exportar")
    path = str(result["path"])
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename=path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1],
        headers={
            "X-Eco-Export-Count": str(result["count"]),
            "X-Eco-Export-Marketplace": str(result["marketplace"]),
        },
    )
