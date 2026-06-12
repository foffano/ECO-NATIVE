from pathlib import Path
from time import time
from urllib.parse import quote, unquote, urlparse

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


def get_r2_client(settings: AppSettings | None = None):
    settings = settings or get_settings()
    if not r2_configured(settings):
        raise RuntimeError("Cloudflare R2 nao configurado.")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.cloudflare_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.cloudflare_r2_access_key,
        aws_secret_access_key=settings.cloudflare_r2_secret_key,
        config=Config(signature_version="s3v4"),
    )


def public_url_to_r2_key(public_url: str, settings: AppSettings | None = None) -> str | None:
    settings = settings or get_settings()
    if not public_url or not settings.cloudflare_r2_public_url:
        return None

    cleaned = public_url.split("?", 1)[0].split("#", 1)[0].strip()
    base = settings.cloudflare_r2_public_url.rstrip("/")
    if cleaned.startswith(base):
        key = cleaned[len(base) :].lstrip("/")
        return unquote(key) if key else None

    parsed = urlparse(cleaned)
    base_parsed = urlparse(base if "://" in base else f"https://{base}")
    if parsed.netloc and parsed.netloc == base_parsed.netloc:
        base_path = base_parsed.path.rstrip("/")
        path = parsed.path
        if base_path and path.startswith(base_path):
            path = path[len(base_path) :]
        key = path.lstrip("/")
        return unquote(key) if key else None
    return None


def _delete_r2_keys(keys: list[str], settings: AppSettings | None = None) -> int:
    if not keys:
        return 0
    settings = settings or get_settings()
    if not r2_configured(settings):
        return 0

    client = get_r2_client(settings)
    deleted = 0
    for index in range(0, len(keys), 1000):
        batch = keys[index : index + 1000]
        response = client.delete_objects(
            Bucket=settings.cloudflare_r2_bucket_name,
            Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
        )
        deleted += len(response.get("Deleted", []))
    return deleted


def delete_r2_prefix(prefix: str, settings: AppSettings | None = None) -> int:
    settings = settings or get_settings()
    if not r2_configured(settings) or not prefix.strip():
        return 0

    client = get_r2_client(settings)
    normalized = prefix.strip("/")
    deleted = 0
    continuation_token: str | None = None

    while True:
        params: dict = {"Bucket": settings.cloudflare_r2_bucket_name, "Prefix": f"{normalized}/"}
        if continuation_token:
            params["ContinuationToken"] = continuation_token
        response = client.list_objects_v2(**params)
        contents = response.get("Contents", [])
        if contents:
            keys = [item["Key"] for item in contents if item.get("Key")]
            deleted += _delete_r2_keys(keys, settings)
        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
    return deleted


def delete_r2_keys(keys: list[str], settings: AppSettings | None = None) -> int:
    unique = sorted({key.strip() for key in keys if key and key.strip()})
    return _delete_r2_keys(unique, settings)


def purge_r2_bucket(settings: AppSettings | None = None) -> dict:
    settings = settings or get_settings()
    if not r2_configured(settings):
        return {"deleted": 0, "bucket": None, "configured": False}

    client = get_r2_client(settings)
    bucket = settings.cloudflare_r2_bucket_name
    deleted = 0
    continuation_token: str | None = None

    while True:
        params: dict = {"Bucket": bucket}
        if continuation_token:
            params["ContinuationToken"] = continuation_token
        response = client.list_objects_v2(**params)
        contents = response.get("Contents", [])
        if contents:
            keys = [item["Key"] for item in contents if item.get("Key")]
            deleted += _delete_r2_keys(keys, settings)
        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")

    return {"deleted": deleted, "bucket": bucket, "configured": True}
