import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.db.store import store
from backend.app.services.auth import (
    SESSION_TTL_SECONDS,
    authenticate,
    cookie_secure_from_headers,
    create_initial_users,
    create_session,
    create_user,
    list_auth_users,
    setup_required,
)
from backend.app.services.store_profiles import ensure_default_store_profile

router = APIRouter()
COOKIE_NAME = "eco_native_session"


class Credentials(BaseModel):
    username: str
    password: str


class LoginPayload(BaseModel):
    """A store signs in by choosing its card; the administrator by login."""
    password: str
    store_profile_id: str | None = None
    username: str | None = None


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
    state = store.snapshot()
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


def _store_logins() -> dict[str, str]:
    """Store id -> login of the stores that can sign in."""
    return {
        str(user["store_profile_id"]): str(user.get("username", ""))
        for user in list_auth_users()
        if user.get("role") == "store" and user.get("store_profile_id") and user.get("enabled", True)
    }


def _login_stores() -> list[dict]:
    # Shown before login: names and logos only, never the logins.
    logins = _store_logins()
    return [
        {"id": profile.id, "name": profile.name, "photo_version": profile.updated_at if profile.logo_path else None}
        for profile in store.snapshot().store_profiles
        if profile.id in logins
    ]


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
    return {
        "authenticated": False,
        "setup_required": needs_setup,
        "legacy_stores": legacy_stores,
        "stores": [] if needs_setup else _login_stores(),
    }


@router.get("/stores/{store_profile_id}/photo")
def store_login_photo(store_profile_id: str) -> FileResponse:
    profile = next((item for item in store.snapshot().store_profiles if item.id == store_profile_id), None)
    if not profile or not profile.logo_path or store_profile_id not in _store_logins():
        raise HTTPException(status_code=404, detail="Foto da loja não encontrada")
    path = Path(profile.logo_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Foto da loja não encontrada")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


# Without a login to type, the password is all that stands between a visitor and
# a store, so repeated wrong passwords lock that store for this visitor a while.
MAX_FAILED_LOGINS = 8
FAILED_LOGIN_WINDOW_SECONDS = 15 * 60
_failed_logins: dict[tuple[str, str], list[float]] = {}
_failed_logins_lock = threading.Lock()


def _client_address(request: Request) -> str:
    # Behind Cloudflare Tunnel every request arrives from the tunnel container.
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "")


def _recent_failures(key: tuple[str, str], now: float) -> list[float]:
    recent = [moment for moment in _failed_logins.get(key, []) if now - moment < FAILED_LOGIN_WINDOW_SECONDS]
    if recent:
        _failed_logins[key] = recent
    else:
        _failed_logins.pop(key, None)
    return recent


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
def login(payload: LoginPayload, request: Request, response: Response) -> dict:
    if payload.store_profile_id:
        username = _store_logins().get(payload.store_profile_id)
        target = f"store:{payload.store_profile_id}"
    else:
        username = (payload.username or "").strip()
        target = f"login:{username.casefold()}"
    key = (_client_address(request), target)
    with _failed_logins_lock:
        if len(_recent_failures(key, time.monotonic())) >= MAX_FAILED_LOGINS:
            raise HTTPException(status_code=429, detail="Muitas tentativas erradas. Aguarde 15 minutos e tente de novo.")
    user = authenticate(username, payload.password) if username else None
    # A store card only opens that store, never the administrator account.
    if user and payload.store_profile_id and user.store_profile_id != payload.store_profile_id:
        user = None
    if not user:
        with _failed_logins_lock:
            _failed_logins.setdefault(key, []).append(time.monotonic())
        raise HTTPException(status_code=401, detail="Senha incorreta" if payload.store_profile_id else "Login ou senha inválidos")
    with _failed_logins_lock:
        _failed_logins.pop(key, None)
    _set_session(response, request, create_session(user))
    request.state.auth = user
    return _session_payload(request)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
