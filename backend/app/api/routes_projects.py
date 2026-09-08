from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.app.db.models import BlockedSourceUrl, Marketplace, Product, Project, StudioState
from backend.app.db.store import store
from backend.app.services.source_url_blacklist import remove_blocked_source_url
from backend.app.services.authorization import current_store_id, require_project, store_project_ids

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    store: str = "Loja principal"
    store_profile_id: str | None = None
    marketplace: Marketplace = Marketplace.shopee
    niche: str = "Utilidades para casa"


@router.get("")
def list_projects(request: Request) -> list[Project]:
    state = store.load()
    allowed = store_project_ids(state, current_store_id(request))
    return sorted((item for item in state.projects if item.id in allowed), key=lambda p: p.created_at, reverse=True)


@router.post("")
def create_project(payload: ProjectCreate, request: Request) -> Project:
    state = store.load()
    store_id = current_store_id(request)
    profile = next((item for item in state.store_profiles if item.id == store_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    data = payload.model_dump()
    data.update(store_profile_id=profile.id, store=profile.name, marketplace=profile.marketplace, niche=profile.niche)
    return store.upsert_project(Project(**data))


@router.get("/{project_id}")
def get_project(project_id: str, request: Request) -> dict[str, Project | list[Product]]:
    state = store.load()
    project = require_project(state, project_id, current_store_id(request))
    products = [p for p in state.products if p.project_id == project_id]
    return {"project": project, "products": products}


@router.get("/{project_id}/blocked-urls")
def list_blocked_urls(project_id: str) -> list[BlockedSourceUrl]:
    state = store.load()
    project = next((item for item in state.projects if item.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto nao encontrado")
    entries = [entry for entry in state.blocked_source_urls if entry.project_id == project_id]
    return sorted(entries, key=lambda entry: entry.created_at, reverse=True)


@router.delete("/{project_id}/blocked-urls/{entry_id}")
def delete_blocked_url(project_id: str, entry_id: str) -> dict:
    preview = store.load()
    project = next((item for item in preview.projects if item.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto nao encontrado")
    if not next((entry for entry in preview.blocked_source_urls if entry.project_id == project_id and entry.id == entry_id), None):
        raise HTTPException(status_code=404, detail="URL bloqueada nao encontrada")

    def apply(state: StudioState) -> dict:
        project = next((item for item in state.projects if item.id == project_id), None)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto nao encontrado")
        removed = remove_blocked_source_url(state, project_id, entry_id)
        if not removed:
            raise HTTPException(status_code=404, detail="URL bloqueada nao encontrada")
        return {"status": "removed", "entry": removed}

    return store.mutate(apply)
