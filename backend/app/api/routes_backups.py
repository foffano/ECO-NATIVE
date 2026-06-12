from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.app.services.store_backup import create_app_backup, restore_backup

router = APIRouter()


@router.get("/download")
def download_app_backup() -> FileResponse:
    path = create_app_backup()
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.get("/stores/{store_profile_id}")
def download_store_backup(store_profile_id: str) -> FileResponse:
    _ = store_profile_id
    path = create_app_backup()
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.post("/restore")
async def restore_backup_route(request: Request) -> dict:
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo de backup vazio")
    if len(content) > 2 * 1024 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Backup maior que 2GB")
    try:
        return restore_backup(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
