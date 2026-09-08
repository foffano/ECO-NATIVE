from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.app.db.models import AiProfile
from backend.app.db.store import store
from backend.app.services.ai_profiles import list_profiles
from backend.app.services.authorization import current_store_id, require_admin

router = APIRouter()


class AiProfileCreate(BaseModel):
    name: str
    prompt: str


class AiProfileUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None


@router.get("")
def get_profiles(request: Request) -> list[AiProfile]:
    state = store.load()
    store_id = current_store_id(request)
    profile = next((item for item in state.store_profiles if item.id == store_id), None)
    return [item for item in list_profiles() if profile and item.id == profile.ai_profile_id]


@router.post("")
def create_profile(payload: AiProfileCreate, request: Request) -> AiProfile:
    require_admin(request)
    return store.upsert_ai_profile(AiProfile(name=payload.name, prompt=payload.prompt))


@router.patch("/{profile_id}")
def update_profile(profile_id: str, payload: AiProfileUpdate, request: Request) -> AiProfile:
    require_admin(request)
    state = store.load()
    profile = next((item for item in state.ai_profiles if item.id == profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil IA nao encontrado")

    if payload.name is not None:
        profile.name = payload.name
    if payload.prompt is not None:
        profile.prompt = payload.prompt

    return store.upsert_ai_profile(profile)
