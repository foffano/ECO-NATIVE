from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.db.models import Marketplace, Product, Project
from backend.app.db.store import store

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
