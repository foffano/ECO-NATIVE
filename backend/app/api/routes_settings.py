from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.paths import DATA_DIR, EXPORTS_DIR, PROJECTS_DIR
from backend.app.core.settings import get_settings, set_env_values

router = APIRouter()


class SettingsUpdate(BaseModel):
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    kie_api_key: str | None = None
    kie_image_model: str | None = None
    use_codex_image_gen: bool | None = None
    codex_bin: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_r2_bucket_name: str | None = None
    cloudflare_r2_access_key: str | None = None
    cloudflare_r2_secret_key: str | None = None
    cloudflare_r2_public_url: str | None = None


@router.get("")
def read_settings() -> dict[str, object]:
    settings = get_settings()
    return {
        "data_dir": str(DATA_DIR),
        "projects_dir": str(PROJECTS_DIR),
        "exports_dir": str(EXPORTS_DIR),
        "integrations": {
            "openrouter": bool(settings.openrouter_api_key),
            "openrouter_model": settings.openrouter_model,
            "kie_ai": bool(settings.kie_api_key),
            "kie_image_model": settings.kie_image_model,
            "codex_image_gen": settings.use_codex_image_gen,
            "codex_bin": settings.codex_bin,
            "cloudflare_r2": bool(
                settings.cloudflare_account_id
                and settings.cloudflare_r2_bucket_name
                and settings.cloudflare_r2_access_key
                and settings.cloudflare_r2_secret_key
                and settings.cloudflare_r2_public_url
            ),
        },
    }


@router.get("/secrets")
def read_setting_secrets() -> dict[str, str | None]:
    settings = get_settings()
    return {
        "openrouter_api_key": settings.openrouter_api_key,
        "openrouter_model": settings.openrouter_model,
        "kie_api_key": settings.kie_api_key,
        "kie_image_model": settings.kie_image_model,
        "codex_bin": settings.codex_bin,
        "cloudflare_account_id": settings.cloudflare_account_id,
        "cloudflare_r2_bucket_name": settings.cloudflare_r2_bucket_name,
        "cloudflare_r2_access_key": settings.cloudflare_r2_access_key,
        "cloudflare_r2_secret_key": settings.cloudflare_r2_secret_key,
        "cloudflare_r2_public_url": settings.cloudflare_r2_public_url,
    }


@router.patch("")
def update_settings(payload: SettingsUpdate) -> dict[str, object]:
    values: dict[str, str] = {}
    if payload.openrouter_api_key:
        values["OPENROUTER_API_KEY"] = payload.openrouter_api_key
    if payload.openrouter_model:
        values["OPENROUTER_MODEL"] = payload.openrouter_model
    if payload.kie_api_key:
        values["KIE_API_KEY"] = payload.kie_api_key
    if payload.kie_image_model:
        values["KIE_IMAGE_MODEL"] = payload.kie_image_model
    if payload.use_codex_image_gen is not None:
        values["USE_CODEX_IMAGE_GEN"] = "true" if payload.use_codex_image_gen else "false"
    if payload.codex_bin is not None:
        values["CODEX_BIN"] = payload.codex_bin
    if payload.cloudflare_account_id:
        values["CLOUDFLARE_ACCOUNT_ID"] = payload.cloudflare_account_id
    if payload.cloudflare_r2_bucket_name:
        values["CLOUDFLARE_R2_BUCKET_NAME"] = payload.cloudflare_r2_bucket_name
    if payload.cloudflare_r2_access_key:
        values["CLOUDFLARE_R2_ACCESS_KEY"] = payload.cloudflare_r2_access_key
    if payload.cloudflare_r2_secret_key:
        values["CLOUDFLARE_R2_SECRET_KEY"] = payload.cloudflare_r2_secret_key
    if payload.cloudflare_r2_public_url:
        values["CLOUDFLARE_R2_PUBLIC_URL"] = payload.cloudflare_r2_public_url

    if values:
        set_env_values(values)

    return read_settings()
