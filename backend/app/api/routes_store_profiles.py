import base64
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.core.paths import DATA_DIR
from backend.app.db.models import Marketplace, StoreProfile
from backend.app.db.store import store
from backend.app.services.store_profiles import list_store_profiles
from backend.app.services.auth import create_user
from backend.app.services.authorization import current_store_id, require_admin

router = APIRouter()


class StoreProfileCreate(BaseModel):
    name: str
    username: str
    password: str
    marketplace: Marketplace = Marketplace.shopee
    niche: str = "Utilidades para casa"
    ai_profile_id: str | None = None
    search_prompt: str = ""
    curation_prompt: str = ""
    listing_prompt: str = ""
    image_prompt: str = ""
    image_prompts: dict[str, str] = Field(default_factory=dict)
    disabled_image_prompts: list[str] = Field(default_factory=list)
    color_variation_prompt: str = ""


class StoreProfileUpdate(BaseModel):
    name: str | None = None
    marketplace: Marketplace | None = None
    niche: str | None = None
    logo_path: str | None = None
    ai_profile_id: str | None = None
    search_prompt: str | None = None
    curation_prompt: str | None = None
    listing_prompt: str | None = None
    image_prompt: str | None = None
    image_prompts: dict[str, str] | None = None
    disabled_image_prompts: list[str] | None = None
    color_variation_prompt: str | None = None


class StoreProfilePhotoUpdate(BaseModel):
    data_url: str


@router.get("")
def get_profiles(request: Request) -> list[StoreProfile]:
    store_id = current_store_id(request)
    return [profile for profile in list_store_profiles() if profile.id == store_id]


@router.post("")
def create_profile(payload: StoreProfileCreate, request: Request) -> StoreProfile:
    require_admin(request)
    profile_data = payload.model_dump(exclude={"username", "password"})
    profile = StoreProfile(**profile_data)
    try:
        create_user(payload.username, payload.password, profile.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return store.upsert_store_profile(profile)


@router.patch("/{profile_id}")
def update_profile(profile_id: str, payload: StoreProfileUpdate) -> StoreProfile:
    state = store.load()
    profile = next((item for item in state.store_profiles if item.id == profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de loja nao encontrado")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(profile, key, value)

    return store.upsert_store_profile(profile)


@router.post("/{profile_id}/photo")
def update_profile_photo(profile_id: str, payload: StoreProfilePhotoUpdate) -> StoreProfile:
    state = store.load()
    profile = next((item for item in state.store_profiles if item.id == profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de loja nao encontrado")

    try:
        header, encoded = payload.data_url.split(",", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Imagem invalida") from exc

    if "image/png" in header:
        extension = ".png"
    elif "image/jpeg" in header or "image/jpg" in header:
        extension = ".jpg"
    elif "image/webp" in header:
        extension = ".webp"
    else:
        raise HTTPException(status_code=400, detail="Formato de imagem nao suportado")

    try:
        content = base64.b64decode(encoded)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Imagem invalida") from exc

    if len(content) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem maior que 4MB")

    logos_dir = DATA_DIR / "store_logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    output = logos_dir / f"{profile.id}{extension}"
    for existing in logos_dir.glob(f"{profile.id}.*"):
        if existing != output:
            existing.unlink(missing_ok=True)
    output.write_bytes(content)
    profile.logo_path = str(output)
    return store.upsert_store_profile(profile)


@router.get("/{profile_id}/photo")
def get_profile_photo(profile_id: str) -> FileResponse:
    state = store.load()
    profile = next((item for item in state.store_profiles if item.id == profile_id), None)
    if not profile or not profile.logo_path:
        raise HTTPException(status_code=404, detail="Foto da loja nao encontrada")

    path = Path(profile.logo_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    return FileResponse(path)
