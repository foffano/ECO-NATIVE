"""Keep earlier versions of generated images when a new one replaces them.

The current image of each style or color keeps its file name, which R2 keys, exports and
downloads rely on. Earlier versions move to a subfolder and stay on the product under a
"previous_" kind, which exports and the current gallery ignore.
"""
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from backend.app.db.models import Asset, Product

PREVIOUS_KIND_PREFIX = "previous_"
PREVIOUS_VERSIONS_DIR = "versoes_anteriores"


def replace_with_new_version(product: Product, kind: str, output_path: Path, render: Callable[[Path], None]) -> None:
    """Render into a temporary file; only a successful render retires the current image."""
    temporary = output_path.with_name(f".novo_{uuid.uuid4().hex}{output_path.suffix}")
    try:
        render(temporary)
        keep_previous_versions(product, kind, output_path)
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)


def keep_previous_versions(product: Product, kind: str, current_path: Path) -> None:
    """Retire every current image of `kind`, and any stray file at its name, as previous versions."""
    retiring = [asset for asset in product.assets if asset.kind == kind]
    if current_path.is_file() and str(current_path) not in {asset.path for asset in retiring}:
        stray = Asset(product_id=product.id, kind=kind, path=str(current_path))
        product.assets.append(stray)
        retiring.append(stray)
    for asset in retiring:
        source = Path(asset.path) if asset.path else None
        if source is None or not source.is_file():
            product.assets.remove(asset)  # Nothing left on disk to keep.
            continue
        target = _previous_version_path(source)
        os.replace(source, target)
        asset.kind = PREVIOUS_KIND_PREFIX + kind
        asset.path = str(target)
        # The R2 object under the current name is about to hold the new version.
        asset.public_url = None


def _previous_version_path(source: Path) -> Path:
    folder = source.parent / PREVIOUS_VERSIONS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = folder / f"{source.stem}_{stamp}{source.suffix}"
    counter = 2
    while target.exists():
        target = folder / f"{source.stem}_{stamp}-{counter}{source.suffix}"
        counter += 1
    return target
