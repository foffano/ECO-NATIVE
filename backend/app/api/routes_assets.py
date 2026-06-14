from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response

from backend.app.db.store import store

router = APIRouter()


def _remote_asset_url(product, asset) -> str | None:
    if asset.public_url and asset.public_url.startswith("http"):
        return asset.public_url
    if asset.kind == "cover_image":
        metadata_url = product.metadata.get("image_url")
        if isinstance(metadata_url, str) and metadata_url.startswith("http"):
            return metadata_url
    return None


@router.get("/{asset_id}", response_model=None)
def get_asset(asset_id: str) -> Response:
    state = store.load()
    for product in state.products:
        asset = next((item for item in product.assets if item.id == asset_id), None)
        if not asset:
            continue

        path = Path(asset.path) if asset.path else None
        if path and path.exists() and path.is_file():
            return FileResponse(path)

        remote_url = _remote_asset_url(product, asset)
        if remote_url:
            return RedirectResponse(remote_url, status_code=307)

        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    raise HTTPException(status_code=404, detail="Asset nao encontrado")
