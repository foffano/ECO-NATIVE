from fastapi import APIRouter, HTTPException, Request

from backend.app.db.models import BlockedSourceUrl, StudioState
from backend.app.db.store import store
from backend.app.services.authorization import current_store_id, store_project_ids
from backend.app.services.source_url_blacklist import remove_blocked_source_url

router = APIRouter()


@router.get("")
def list_blocked_urls(request: Request) -> list[BlockedSourceUrl]:
    state = store.snapshot()
    allowed = store_project_ids(state, current_store_id(request))
    entries = [entry for entry in state.blocked_source_urls if entry.project_id in allowed]
    return sorted(entries, key=lambda entry: entry.created_at, reverse=True)


@router.delete("/{entry_id}")
def delete_blocked_url(entry_id: str, request: Request) -> dict:
    store_id = current_store_id(request)

    def apply(state: StudioState) -> dict:
        allowed = store_project_ids(state, store_id)
        entry = next(
            (item for item in state.blocked_source_urls if item.id == entry_id and item.project_id in allowed),
            None,
        )
        removed = entry and remove_blocked_source_url(state, entry.project_id, entry_id)
        if not removed:
            raise HTTPException(status_code=404, detail="URL bloqueada não encontrada")
        return {"status": "removed", "entry": removed}

    return store.mutate(apply)
