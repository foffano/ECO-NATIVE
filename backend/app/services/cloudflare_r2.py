from pathlib import Path
from time import time
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from backend.app.core.settings import AppSettings, get_settings


def r2_configured(settings: AppSettings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(
        settings.cloudflare_account_id
        and settings.cloudflare_r2_bucket_name
        and settings.cloudflare_r2_access_key
        and settings.cloudflare_r2_secret_key
        and settings.cloudflare_r2_public_url
    )


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".png":
        return "image/png"
    return "application/octet-stream"


def public_url_for_key(key: str, settings: AppSettings) -> str:
    return f"{settings.cloudflare_r2_public_url.rstrip('/')}/{quote(key)}"


def upload_file_to_r2(local_path: str | Path, key_prefix: str = "eco-native", force: bool = False) -> str:
    settings = get_settings()
    if not r2_configured(settings):
        raise RuntimeError("Cloudflare R2 não configurado. Configure R2 em Ajustes para gerar URLs públicas permanentes.")

    path = Path(local_path)
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"Arquivo não encontrado para upload R2: {path}")

    key = f"{key_prefix.strip('/')}/{path.name}"
    public_url = public_url_for_key(key, settings)

    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.cloudflare_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.cloudflare_r2_access_key,
        aws_secret_access_key=settings.cloudflare_r2_secret_key,
        config=Config(signature_version="s3v4"),
    )

    if not force:
        try:
            s3.head_object(Bucket=settings.cloudflare_r2_bucket_name, Key=key)
            return public_url
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code not in {"404", "NoSuchKey", "NotFound"}:
                raise

    s3.upload_file(
        Filename=str(path),
        Bucket=settings.cloudflare_r2_bucket_name,
        Key=key,
        ExtraArgs={"ContentType": content_type_for(path)},
    )
    return f"{public_url}?v={int(time())}" if force else public_url
