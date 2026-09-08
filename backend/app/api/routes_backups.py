from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.app.services.store_backup import create_store_backup, read_manifest, restore_store_backup
from backend.app.services.authorization import current_store_id

router = APIRouter()


@router.get("/download")
def download_app_backup(request: Request) -> FileResponse:
    path = create_store_backup(current_store_id(request))
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.get("/stores/{store_profile_id}")
def download_store_backup(store_profile_id: str, request: Request) -> FileResponse:
    if store_profile_id != current_store_id(request):
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    path = create_store_backup(store_profile_id)
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.post("/restore")
async def restore_backup_route(request: Request) -> dict:
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo de backup vazio")
    if len(content) > 2 * 1024 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Backup maior que 2GB")
    try:
        archive, manifest = read_manifest(content)
        archive.close()
        if manifest.get("kind") == "full_app" or manifest.get("store_profile_id") != current_store_id(request):
            raise HTTPException(status_code=403, detail="Este login só pode restaurar um backup da própria loja")
        return restore_store_backup(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
