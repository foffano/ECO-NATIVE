import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from backend.app.core.paths import DATA_DIR

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = Path(os.getenv("ECO_NATIVE_ENV_PATH", DATA_DIR / ".env")).expanduser().resolve()
if not os.getenv("ECO_NATIVE_ENV_PATH") and (PROJECT_ROOT / ".env").exists():
    ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class AppSettings:
    openrouter_api_key: str | None
    openrouter_model: str | None
    kie_api_key: str | None
    kie_image_model: str | None
    cloudflare_account_id: str | None
    cloudflare_r2_bucket_name: str | None
    cloudflare_r2_access_key: str | None
    cloudflare_r2_secret_key: str | None
    cloudflare_r2_public_url: str | None


def get_settings() -> AppSettings:
    load_dotenv(ENV_PATH, override=True)
    return AppSettings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "qwen/qwen3.5-flash-02-23"),
        kie_api_key=os.getenv("KIE_API_KEY") or os.getenv("KIEAI_API_KEY"),
        kie_image_model=os.getenv("KIE_IMAGE_MODEL", "qwen/image-edit"),
        cloudflare_account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        cloudflare_r2_bucket_name=os.getenv("CLOUDFLARE_R2_BUCKET_NAME"),
        cloudflare_r2_access_key=os.getenv("CLOUDFLARE_R2_ACCESS_KEY"),
        cloudflare_r2_secret_key=os.getenv("CLOUDFLARE_R2_SECRET_KEY"),
        cloudflare_r2_public_url=os.getenv("CLOUDFLARE_R2_PUBLIC_URL"),
    )


def set_env_values(values: dict[str, str]) -> None:
    existing: dict[str, str] = {}
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()

    for key, value in values.items():
        if value.strip():
            existing[key] = value.strip()

    content = "\n".join(f"{key}={value}" for key, value in sorted(existing.items())) + "\n"
    ENV_PATH.write_text(content, encoding="utf-8")

    for key, value in existing.items():
        os.environ[key] = value
