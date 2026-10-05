import logging
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

from backend.app.core.paths import CACHE_DIR

logger = logging.getLogger(__name__)

THUMBS_DIR = CACHE_DIR / "thumbs"
THUMB_WIDTHS = (160, 384, 768)
THUMB_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def thumb_width(requested: int) -> int:
    """Snap a requested width to one of the cached sizes."""
    return next((width for width in THUMB_WIDTHS if width >= requested), THUMB_WIDTHS[-1])


def thumbnail_for(asset_id: str, source: Path, width: int) -> Path | None:
    """Return a cached WebP thumbnail of `source`, creating it on first use.

    The cache key includes the source mtime and size, so replacing an image
    (which keeps its asset id) produces a new thumbnail. Returns None when the
    file is not an image Pillow can read; callers then serve the original.
    """
    if source.suffix.lower() not in THUMB_SUFFIXES:
        return None
    stat = source.stat()
    target = THUMBS_DIR / f"{asset_id}_{stat.st_mtime_ns}_{stat.st_size}_{width}.webp"
    if target.is_file():
        return target

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "A" in image.getbands() or image.mode == "P" else "RGB")
            image.thumbnail((width, width), Image.Resampling.LANCZOS)
            handle, temporary = tempfile.mkstemp(prefix=f".{asset_id}_", suffix=".webp", dir=THUMBS_DIR)
            os.close(handle)
            try:
                image.save(temporary, "WEBP", quality=80, method=4)
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        logger.warning("Miniatura nao gerada para %s: %s", source, error)
        return None

    for stale in THUMBS_DIR.glob(f"{asset_id}_*_{width}.webp"):
        if stale != target:
            stale.unlink(missing_ok=True)
    return target
