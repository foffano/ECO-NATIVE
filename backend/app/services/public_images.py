"""Public links to product images, served by the app itself.

Kie.ai and the Shopee mass upload download images by URL. Each link carries a
signature of the file path made with the server secret, so it cannot be guessed
and works only for that file; the rest of the app still needs a login. A link
stops working when its file is deleted.
"""
import base64
import hashlib
import hmac
from pathlib import Path
from urllib.parse import quote

from backend.app.core.paths import PROJECTS_DIR
from backend.app.core.settings import get_settings
from backend.app.db.models import StudioState
from backend.app.db.store import store

PUBLIC_IMAGE_PREFIX = "/i"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class PublicUrlMissing(RuntimeError):
    pass


def public_base_url() -> str:
    base = (get_settings().public_app_url or "").strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise PublicUrlMissing(
            "Configure o endereço público do app em Ajustes → Integrações "
            "(ex.: https://eco.seudominio.com) para enviar imagens ao Kie.ai e à Shopee."
        )
    return base


def _signature(relative: str) -> str:
    from backend.app.services.auth import _secret

    key = hmac.new(_secret(), b"public-images", hashlib.sha256).digest()
    digest = hmac.new(key, relative.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")[:32]


def _relative_image_path(path: str | Path) -> str | None:
    try:
        resolved = Path(path).resolve()
        relative = resolved.relative_to(PROJECTS_DIR.resolve())
    except (OSError, ValueError):
        return None
    if resolved.suffix.lower() not in IMAGE_SUFFIXES:
        return None
    return relative.as_posix()


def public_image_url(path: str | Path) -> str:
    """Public link to an image stored with the products."""
    relative = _relative_image_path(path)
    if relative is None or not Path(path).is_file():
        raise RuntimeError(f"Imagem não encontrada para gerar link público: {Path(path).name}")
    return f"{public_base_url()}{PUBLIC_IMAGE_PREFIX}/{_signature(relative)}/{quote(relative)}"


def resolve_public_image(signature: str, relative: str) -> Path | None:
    """The file a public link points to, or None for a wrong or stale link."""
    candidate = PROJECTS_DIR / relative
    checked = _relative_image_path(candidate)
    if checked is None or checked != Path(relative).as_posix():
        return None
    if not hmac.compare_digest(signature, _signature(checked)):
        return None
    return candidate if candidate.is_file() else None


def forget_r2_links() -> int:
    """Drop image links left from the Cloudflare R2 bucket, which the app no longer uses.

    Afterwards `public_url` only keeps where a captured cover came from.
    """
    def expected(product, asset) -> str | None:
        source = product.metadata.get("image_url")
        if asset.kind == "cover_image" and isinstance(source, str) and source.startswith("http"):
            return source
        return None

    snapshot = store.snapshot()
    if all(asset.public_url == expected(product, asset) for product in snapshot.products for asset in product.assets):
        return 0

    def apply(state: StudioState) -> int:
        changed = 0
        for product in state.products:
            for asset in product.assets:
                if asset.public_url != expected(product, asset):
                    asset.public_url = expected(product, asset)
                    changed += 1
        return changed

    return store.mutate(apply)
