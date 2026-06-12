from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.db.models import BlockedSourceUrl, Marketplace, Product, Project
from backend.app.db.store import store
from backend.app.services.source_url_blacklist import remove_blocked_source_url

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    store: str = "Loja principal"
    store_profile_id: str | None = None
    marketplace: Marketplace = Marketplace.shopee
    niche: str = "Utilidades para casa"


@router.get("")
def list_projects() -> list[Project]:
    return sorted(store.load().projects, key=lambda p: p.created_at, reverse=True)


@router.post("")
def create_project(payload: ProjectCreate) -> Project:
    return store.upsert_project(Project(**payload.model_dump()))


@router.get("/{project_id}")
def get_project(project_id: str) -> dict[str, Project | list[Product]]:
    state = store.load()
    project = next((p for p in state.projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto nao encontrado")
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
    state = store.load()
    project = next((item for item in state.projects if item.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto nao encontrado")
    removed = remove_blocked_source_url(state, project_id, entry_id)
    if not removed:
        raise HTTPException(status_code=404, detail="URL bloqueada nao encontrada")
    store.save(state)
    return {"status": "removed", "entry": removed}
