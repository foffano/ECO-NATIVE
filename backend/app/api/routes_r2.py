from fastapi import APIRouter, HTTPException, Request

from backend.app.db.models import StudioState
from backend.app.db.store import store
from backend.app.services.cloudflare_r2 import purge_r2_bucket, r2_configured
from backend.app.services.authorization import require_admin

router = APIRouter()


def _clear_stored_public_urls() -> int:
    """Limpa o public_url de todos os assets no store.

    Apos esvaziar o bucket os objetos nao existem mais; manter o public_url
    gravado faria a IA receber URLs que apontam para imagens inexistentes.
    """

    def apply(state: StudioState) -> int:
        cleared = 0
        for product in state.products:
            for asset in product.assets:
                if asset.public_url:
                    asset.public_url = None
                    cleared += 1
        return cleared

    return store.mutate(apply)


@router.post("/purge-bucket")
def purge_bucket(request: Request, confirm: bool = False) -> dict:
    require_admin(request)
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Esta acao apaga todos os arquivos do bucket R2 configurado. Use ?confirm=true para confirmar.",
        )
    if not r2_configured():
        raise HTTPException(status_code=400, detail="Cloudflare R2 nao configurado.")
    result = purge_r2_bucket()
    result["cleared_public_urls"] = _clear_stored_public_urls()
    return result
