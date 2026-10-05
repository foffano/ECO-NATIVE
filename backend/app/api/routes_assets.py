from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from backend.app.db.store import store
from backend.app.services.thumbnails import thumb_width, thumbnail_for

router = APIRouter()

# URLs carrying ?v= change whenever the product is saved, so the browser can
# keep them without asking again. The version has one-second resolution, so the
# lifetime stays bounded. Unversioned URLs are revalidated through the ETag.
VERSIONED_CACHE = "private, max-age=604800"
UNVERSIONED_CACHE = "private, no-cache"


def _remote_asset_url(product, asset) -> str | None:
    if asset.public_url and asset.public_url.startswith("http"):
        return asset.public_url
    if asset.kind == "cover_image":
        metadata_url = product.metadata.get("image_url")
        if isinstance(metadata_url, str) and metadata_url.startswith("http"):
            return metadata_url
    return None


def _file_response(request: Request, path: Path, cache_control: str) -> Response:
    stat = path.stat()
    etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
    headers = {"Cache-Control": cache_control, "ETag": etag}
    if etag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers=headers)
    return FileResponse(path, headers=headers)


@router.get("/{asset_id}", response_model=None)
def get_asset(asset_id: str, request: Request, v: str | None = None, w: int | None = None) -> Response:
    found = store.find_asset(asset_id)
    if not found:
        raise HTTPException(status_code=404, detail="Asset nao encontrado")
    product, asset = found
    cache_control = VERSIONED_CACHE if v else UNVERSIONED_CACHE

    path = Path(asset.path) if asset.path else None
    if path and path.is_file():
        if w and w > 0:
            thumbnail = thumbnail_for(asset.id, path, thumb_width(w))
            if thumbnail:
                return _file_response(request, thumbnail, cache_control)
        return _file_response(request, path, cache_control)

    remote_url = _remote_asset_url(product, asset)
    if remote_url:
        return RedirectResponse(remote_url, status_code=307)

    raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
