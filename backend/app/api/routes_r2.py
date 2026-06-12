from fastapi import APIRouter, HTTPException

from backend.app.services.cloudflare_r2 import purge_r2_bucket, r2_configured

router = APIRouter()


@router.post("/purge-bucket")
def purge_bucket(confirm: bool = False) -> dict:
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Esta acao apaga todos os arquivos do bucket R2 configurado. Use ?confirm=true para confirmar.",
        )
    if not r2_configured():
        raise HTTPException(status_code=400, detail="Cloudflare R2 nao configurado.")
    return purge_r2_bucket()
