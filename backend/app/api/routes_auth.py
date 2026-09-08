from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.app.db.store import store
from backend.app.services.auth import (
    SESSION_TTL_SECONDS,
    authenticate,
    cookie_secure_from_headers,
    create_initial_users,
    create_session,
    create_user,
    setup_required,
)
from backend.app.services.store_profiles import ensure_default_store_profile

router = APIRouter()
COOKIE_NAME = "eco_native_session"


class Credentials(BaseModel):
    username: str
    password: str


class InitialStoreCredential(Credentials):
    store_profile_id: str


class SetupPayload(BaseModel):
    admin: Credentials
    stores: list[InitialStoreCredential]
    store_name: str | None = None


def _set_session(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=cookie_secure_from_headers(request.headers),
        samesite="strict",
        path="/",
    )


def _session_payload(request: Request) -> dict:
    user = request.state.auth
    if user.is_admin:
        return {
            "authenticated": True,
            "setup_required": False,
            "username": user.username,
            "is_admin": True,
            "store": None,
        }
    state = store.load()
    profile = next((item for item in state.store_profiles if item.id == user.store_profile_id), None)
    if not profile:
        raise HTTPException(status_code=401, detail="A loja deste login não existe mais")
    return {
        "authenticated": True,
        "setup_required": False,
        "username": user.username,
        "is_admin": user.is_admin,
        "store": profile,
    }


@router.get("/status")
def status(request: Request) -> dict:
    if getattr(request.state, "auth", None):
        return _session_payload(request)
    needs_setup = setup_required()
    legacy_stores = []
    if needs_setup:
        profiles = store.load().store_profiles
        if not profiles:
            profiles = [ensure_default_store_profile()]
        legacy_stores = [{"id": profile.id, "name": profile.name} for profile in profiles]
    return {"authenticated": False, "setup_required": needs_setup, "legacy_stores": legacy_stores}


@router.post("/setup")
def setup(payload: SetupPayload, request: Request, response: Response) -> dict:
    if not setup_required():
        raise HTTPException(status_code=409, detail="O acesso inicial já foi configurado")
    profiles = store.load().store_profiles
    if not profiles:
        profiles = [ensure_default_store_profile()]
    expected_ids = {profile.id for profile in profiles}
    received_ids = {item.store_profile_id for item in payload.stores}
    if received_ids != expected_ids or len(payload.stores) != len(profiles):
        raise HTTPException(status_code=400, detail="Configure um acesso para cada loja existente")
    if len(profiles) == 1 and payload.store_name and payload.store_name.strip():
        profiles[0].name = payload.store_name.strip()
        store.upsert_store_profile(profiles[0])
    try:
        user = create_initial_users(
            (payload.admin.username, payload.admin.password),
            [(item.username, item.password, item.store_profile_id) for item in payload.stores],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_session(response, request, create_session(user))
    request.state.auth = user
    return _session_payload(request)


@router.post("/login")
def login(payload: Credentials, request: Request, response: Response) -> dict:
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Login ou senha inválidos")
    _set_session(response, request, create_session(user))
    request.state.auth = user
    return _session_payload(request)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
