from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.db.models import Marketplace
from backend.app.services.exporter import export_marketplace_csv

router = APIRouter()


class ExportRequest(BaseModel):
    project_id: str
    marketplace: Marketplace = Marketplace.shopee
    product_ids: list[str] = []


@router.post("")
def create_export(payload: ExportRequest) -> dict[str, str | int]:
    result = export_marketplace_csv(
        project_id=payload.project_id,
        marketplace=payload.marketplace,
        product_ids=payload.product_ids,
    )
    if not result:
        raise HTTPException(status_code=400, detail="Nenhum produto valido para exportar")
    return result
