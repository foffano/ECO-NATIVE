import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.paths import DATA_DIR


AUTH_PATH = DATA_DIR / "auth.json"
SECRET_PATH = DATA_DIR / ".session-secret"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30


@dataclass(frozen=True)
class AuthenticatedStore:
    store_profile_id: str | None
    username: str
    is_admin: bool = False


def _read_auth() -> dict:
    if not AUTH_PATH.exists():
        return {"users": []}
    try:
        payload = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"version": 2, "users": []}
        return _migrate_auth_payload(payload)
    except (OSError, json.JSONDecodeError):
        return {"users": []}


def _unique_store_username(base: str, users: list[dict]) -> str:
    taken = {_normalize_username(str(item.get("username", ""))) for item in users}
    candidate = f"{base}-loja"
    index = 2
    while candidate in taken:
        candidate = f"{base}-loja-{index}"
        index += 1
    return candidate


def _migrate_auth_payload(payload: dict) -> dict:
    if int(payload.get("version") or 1) >= 2:
        return payload
    users = [dict(item) for item in payload.get("users", []) if isinstance(item, dict)]
    admin = next((item for item in users if item.get("is_admin")), users[0] if users else None)
    if admin and admin.get("store_profile_id"):
        store_user = dict(admin)
        store_user["username"] = _unique_store_username(_normalize_username(str(admin.get("username", "admin"))), users)
        store_user["role"] = "store"
        store_user["is_admin"] = False
        store_user["created_at"] = int(time.time())
        users.append(store_user)
    for item in users:
        if item is admin:
            item["role"] = "admin"
            item["is_admin"] = True
            item["store_profile_id"] = None
        else:
            item["role"] = "store"
            item["is_admin"] = False
        item.setdefault("enabled", True)
        item.setdefault("quotas", {})
    migrated = {**payload, "version": 2, "users": users}
    backup = AUTH_PATH.with_name("auth.pre-admin-migration.json")
    if AUTH_PATH.exists() and not backup.exists():
        shutil.copy2(AUTH_PATH, backup)
    _write_auth(migrated)
    return migrated


def _write_auth(payload: dict) -> None:
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = AUTH_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(AUTH_PATH)


def setup_required() -> bool:
    return not bool(_read_auth().get("users"))


def _normalize_username(username: str) -> str:
    return username.strip().casefold()


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return f"pbkdf2_sha256$600000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_user(username: str, password: str, store_profile_id: str) -> AuthenticatedStore:
    normalized = _normalize_username(username)
    if len(normalized) < 3:
        raise ValueError("O login precisa ter pelo menos 3 caracteres")
    if len(password) < 8:
        raise ValueError("A senha precisa ter pelo menos 8 caracteres")
    payload = _read_auth()
    users = payload.setdefault("users", [])
    if any(_normalize_username(str(user.get("username", ""))) == normalized for user in users):
        raise ValueError("Este login já está em uso")
    users.append({
        "username": normalized,
        "password_hash": _password_hash(password),
        "store_profile_id": store_profile_id,
        "role": "store",
        "is_admin": False,
        "enabled": True,
        "quotas": {},
        "created_at": int(time.time()),
    })
    _write_auth(payload)
    return AuthenticatedStore(store_profile_id=store_profile_id, username=normalized, is_admin=False)


def create_initial_users(admin_entry: tuple[str, str], entries: list[tuple[str, str, str]]) -> AuthenticatedStore:
    """Create the first credentials atomically so a migration cannot be half configured."""
    if not setup_required():
        raise ValueError("O acesso inicial já foi configurado")
    prepared: list[tuple[str, str, str]] = []
    admin_username, admin_password = admin_entry
    normalized_admin = _normalize_username(admin_username)
    if len(normalized_admin) < 3 or len(admin_password) < 8:
        raise ValueError("O administrador precisa de login com 3 caracteres e senha com 8 caracteres")
    usernames: set[str] = {normalized_admin}
    store_ids: set[str] = set()
    for username, password, store_profile_id in entries:
        normalized = _normalize_username(username)
        if len(normalized) < 3:
            raise ValueError("Todos os logins precisam ter pelo menos 3 caracteres")
        if len(password) < 8:
            raise ValueError("Todas as senhas precisam ter pelo menos 8 caracteres")
        if normalized in usernames:
            raise ValueError("Cada loja precisa ter um login diferente")
        if store_profile_id in store_ids:
            raise ValueError("Há uma loja repetida na configuração")
        usernames.add(normalized)
        store_ids.add(store_profile_id)
        prepared.append((normalized, password, store_profile_id))

    payload = {"version": 2, "users": [{
        "username": normalized_admin,
        "password_hash": _password_hash(admin_password),
        "store_profile_id": None,
        "role": "admin",
        "is_admin": True,
        "enabled": True,
        "quotas": {},
        "created_at": int(time.time()),
    }, *[
        {
            "username": username,
            "password_hash": _password_hash(password),
            "store_profile_id": store_profile_id,
            "role": "store",
            "is_admin": False,
            "enabled": True,
            "quotas": {},
            "created_at": int(time.time()),
        }
        for username, password, store_profile_id in prepared
    ]]}
    _write_auth(payload)
    return AuthenticatedStore(store_profile_id=None, username=normalized_admin, is_admin=True)


def authenticate(username: str, password: str) -> AuthenticatedStore | None:
    normalized = _normalize_username(username)
    for index, user in enumerate(_read_auth().get("users", [])):
        if _normalize_username(str(user.get("username", ""))) != normalized:
            continue
        if user.get("enabled", True) and _password_matches(password, str(user.get("password_hash", ""))):
            return AuthenticatedStore(
                store_profile_id=str(user["store_profile_id"]) if user.get("store_profile_id") else None,
                username=normalized,
                is_admin=user.get("role") == "admin",
            )
    # Make unknown-user attempts cost roughly the same as known-user attempts.
    _password_hash(password, b"eco-native-auth")
    return None


def _secret() -> bytes:
    if not SECRET_PATH.exists():
        SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        SECRET_PATH.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return SECRET_PATH.read_text(encoding="utf-8").strip().encode("utf-8")


def create_session(user: AuthenticatedStore) -> str:
    payload = {
        "store_profile_id": user.store_profile_id,
        "username": user.username,
        "is_admin": user.is_admin,
        "expires": int(time.time()) + SESSION_TTL_SECONDS,
        "nonce": secrets.token_hex(8),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def read_session(token: str | None) -> AuthenticatedStore | None:
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if int(payload["expires"]) < int(time.time()):
            return None
        username = _normalize_username(str(payload["username"]))
        record = next(
            (item for item in _read_auth().get("users", []) if _normalize_username(str(item.get("username", ""))) == username),
            None,
        )
        if not record or not record.get("enabled", True):
            return None
        is_admin = record.get("role") == "admin"
        return AuthenticatedStore(
            store_profile_id=None if is_admin else str(record.get("store_profile_id") or "") or None,
            username=username,
            is_admin=is_admin,
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _is_admin_username(username: str) -> bool:
    normalized = _normalize_username(username)
    for index, user in enumerate(_read_auth().get("users", [])):
        if _normalize_username(str(user.get("username", ""))) == normalized:
            return bool(user.get("is_admin", index == 0))
    return False


def list_auth_users() -> list[dict]:
    return [dict(item) for item in _read_auth().get("users", [])]


def update_store_access(store_profile_id: str, *, enabled: bool, quotas: dict[str, int | float | None]) -> dict:
    payload = _read_auth()
    user = next(
        (item for item in payload.get("users", []) if item.get("role") == "store" and item.get("store_profile_id") == store_profile_id),
        None,
    )
    if not user:
        raise ValueError("Login da loja não encontrado")
    user["enabled"] = bool(enabled)
    user["quotas"] = quotas
    _write_auth(payload)
    return dict(user)


def cookie_secure_from_headers(headers) -> bool:
    forwarded = headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    return forwarded == "https" or os.getenv("ECO_NATIVE_SECURE_COOKIES", "").lower() in {"1", "true", "yes"}
