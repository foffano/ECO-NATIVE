"""Download, validate and repair product cover images."""

from __future__ import annotations

import logging
import mimetypes
import zlib
from pathlib import Path

from PIL import Image

from backend.app.db.models import Asset, Product
from backend.app.services.cloudflare_r2 import r2_configured, upload_file_to_r2
from backend.app.services.http_client import HttpResponseError, download as http_download
from backend.app.services.product_paths import cover_image_filename, product_assets_dir


def r2_key_prefix(product: Product) -> str:
    return f"eco-native/{product.project_id}/{product.id}"

logger = logging.getLogger(__name__)


class CoverImageError(RuntimeError):
    pass


def sniff_image_format(data: bytes) -> str | None:
    if not data:
        return None
    if data[:2] == b"\x1f\x8b":
        return "gzip"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return "webp"
    return None


def mime_type_for_image(data: bytes, path: Path) -> str:
    detected = sniff_image_format(data)
    if detected == "jpeg":
        return "image/jpeg"
    if detected == "png":
        return "image/png"
    if detected == "webp":
        return "image/webp"
    guessed = mimetypes.guess_type(path.name)[0]
    return guessed or "image/jpeg"


def validate_cover_bytes(data: bytes, path: Path) -> None:
    detected = sniff_image_format(data)
    if not data:
        raise CoverImageError(f"Imagem vazia: {path.name}")
    if detected == "gzip":
        raise CoverImageError(
            f"A capa do produto parece corrompida ({path.name}). "
            "O app vai tentar baixar novamente da URL original."
        )
    if detected in {"jpeg", "png", "webp"}:
        return
    raise CoverImageError(
        f"Formato de imagem nao suportado para capa ({path.name}). Use JPG, PNG ou WEBP."
    )


def cover_source_url(product: Product, cover: Asset) -> str | None:
    for candidate in (cover.public_url, product.metadata.get("image_url")):
        if isinstance(candidate, str) and candidate.startswith("http"):
            return candidate
    return None


def download_cover_file(project_id: str, sku: str, image_url: str, output_path: Path | None = None) -> Path:
    destination = output_path or (product_assets_dir(project_id, sku) / cover_image_filename(sku))
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        http_download(image_url, destination, timeout=60)
    except HttpResponseError as exc:
        raise CoverImageError(f"Falha ao baixar capa do produto: {exc}") from exc

    data = destination.read_bytes()
    if sniff_image_format(data) == "gzip":
        destination.unlink(missing_ok=True)
        raise CoverImageError("Capa baixada veio comprimida de forma invalida. Tente coletar o produto novamente.")
    normalize_cover_to_jpeg(destination)
    return destination


def normalize_cover_to_jpeg(path: Path) -> bool:
    data = path.read_bytes()
    detected = sniff_image_format(data)
    if detected == "jpeg":
        return False
    if detected not in {"png", "webp"}:
        return False

    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            rgb.save(path, format="JPEG", quality=92)
    except zlib.error as exc:
        raise CoverImageError(
            f"Imagem corrompida ({path.name}). O app vai tentar baixar novamente da URL original."
        ) from exc
    except OSError as exc:
        raise CoverImageError(f"Nao foi possivel ler a imagem ({path.name}): {exc}") from exc
    return True


def repair_cover_file(path: Path, image_url: str | None, *, project_id: str, sku: str) -> None:
    needs_download = not path.is_file()
    if path.is_file():
        detected = sniff_image_format(path.read_bytes())
        needs_download = detected in {None, "gzip"}
        if detected == "webp":
            try:
                normalize_cover_to_jpeg(path)
                return
            except CoverImageError:
                path.unlink(missing_ok=True)
                needs_download = True

    if not needs_download:
        try:
            validate_cover_bytes(path.read_bytes(), path)
            if sniff_image_format(path.read_bytes()) in {"png", "webp"}:
                normalize_cover_to_jpeg(path)
            return
        except CoverImageError:
            path.unlink(missing_ok=True)
            needs_download = True

    if not needs_download:
        return

    if not image_url:
        raise CoverImageError(
            f"Capa ausente ou corrompida ({path.name}) e produto sem URL de imagem para reparo."
        )

    download_cover_file(project_id, sku, image_url, path)


def ensure_product_cover(product: Product) -> Asset:
    cover = next((asset for asset in product.assets if asset.kind == "cover_image"), None)
    if not cover:
        raise CoverImageError("Produto sem imagem capturada.")

    sku = str(product.metadata.get("sku") or "").strip().upper()
    if not sku:
        raise CoverImageError("Produto sem SKU.")

    path = Path(cover.path) if cover.path else product_assets_dir(product.project_id, sku) / cover_image_filename(sku)
    if not cover.path or path.name != cover_image_filename(sku):
        target = product_assets_dir(product.project_id, sku) / cover_image_filename(sku)
        if path.is_file() and path != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(path.read_bytes())
            path = target
        elif not path.is_file():
            path = target
        cover.path = str(path)

    source_url = cover_source_url(product, cover)
    try:
        repair_cover_file(path, source_url, project_id=product.project_id, sku=sku)
    except CoverImageError:
        raise
    except Exception as exc:
        raise CoverImageError(f"Falha ao preparar capa ({path.name}): {exc}") from exc

    validate_cover_bytes(path.read_bytes(), path)
    return cover


def cover_r2_public_url(product: Product, cover: Asset | None = None) -> str:
    """Publica a capa local no R2 e retorna a URL publica usada pela IA."""
    if not r2_configured():
        raise CoverImageError(
            "Cloudflare R2 nao configurado. Configure R2 em Ajustes para enviar a capa capturada a IA."
        )

    cover = cover or ensure_product_cover(product)
    path = Path(cover.path)
    if not path.is_file():
        raise CoverImageError("Capa local nao encontrada no disco.")

    try:
        public_url = upload_file_to_r2(path, r2_key_prefix(product), force=True)
    except Exception as exc:
        raise CoverImageError(f"Falha ao publicar capa no R2: {exc}") from exc

    cover.public_url = public_url
    return public_url


def repair_product_cover(product: Product) -> Asset:
    return ensure_product_cover(product)


def repair_all_product_covers(products: list[Product]) -> dict[str, int | list[str]]:
    repaired = 0
    failed: list[str] = []
    for product in products:
        sku = str(product.metadata.get("sku") or product.id).strip()
        try:
            repair_product_cover(product)
            repaired += 1
        except CoverImageError as exc:
            failed.append(f"{sku}: {exc}")
    return {"repaired": repaired, "failed": failed, "failed_count": len(failed)}
