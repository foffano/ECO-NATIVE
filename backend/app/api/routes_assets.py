from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.db.store import store

router = APIRouter()


@router.get("/{asset_id}")
def get_asset(asset_id: str) -> FileResponse:
    state = store.load()
    for product in state.products:
        asset = next((item for item in product.assets if item.id == asset_id), None)
        if not asset:
            continue

        path = Path(asset.path)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

        return FileResponse(path)

    raise HTTPException(status_code=404, detail="Asset nao encontrado")
