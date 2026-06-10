from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.db.models import AiProfile
from backend.app.db.store import store
from backend.app.services.ai_profiles import list_profiles

router = APIRouter()


class AiProfileCreate(BaseModel):
    name: str
    prompt: str


class AiProfileUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None


@router.get("")
def get_profiles() -> list[AiProfile]:
    return list_profiles()


@router.post("")
def create_profile(payload: AiProfileCreate) -> AiProfile:
    return store.upsert_ai_profile(AiProfile(name=payload.name, prompt=payload.prompt))


@router.patch("/{profile_id}")
def update_profile(profile_id: str, payload: AiProfileUpdate) -> AiProfile:
    state = store.load()
    profile = next((item for item in state.ai_profiles if item.id == profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil IA nao encontrado")

    if payload.name is not None:
        profile.name = payload.name
    if payload.prompt is not None:
        profile.prompt = payload.prompt

    return store.upsert_ai_profile(profile)
