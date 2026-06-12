"""Migra produtos existentes para pastas e arquivos identificados por SKU."""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.paths import DATA_DIR, PROJECTS_DIR  # noqa: E402
from backend.app.db.models import Product, Project, StoreProfile, StudioState  # noqa: E402
from backend.app.services.product_paths import (  # noqa: E402
    color_variation_filename,
    cover_image_filename,
    model_filename,
    product_assets_dir,
    safe_sku_folder,
    studio_image_filename,
)
from backend.app.services.sku import ensure_color_skus, ensure_product_sku  # noqa: E402
from backend.app.services.store_profiles import get_store_profile  # noqa: E402


def safe_folder_name(value: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", value.strip())
    return cleaned[:120] or "produto"


def filename_from_public_url(public_url: str | None) -> str | None:
    if not public_url:
        return None
    name = public_url.split("/")[-1].split("?")[0].strip()
    return name or None


def target_filename(sku: str, kind: str, original_path: Path, public_url: str | None) -> str:
    url_name = filename_from_public_url(public_url)
    if url_name:
        if url_name.startswith(f"{sku}_"):
            return url_name
        if url_name.startswith("capa_produto"):
            return f"{sku}_{url_name}"
        if url_name.startswith("model"):
            return model_filename(sku, Path(url_name).suffix or original_path.suffix or ".3mf")

    if kind == "cover_image":
        suffix = original_path.suffix or ".jpg"
        return cover_image_filename(sku) if suffix.lower() == ".jpg" else f"{sku}_capa_produto{suffix}"
    if kind == "model_3mf":
        return model_filename(sku, original_path.suffix or ".3mf")
    if kind.startswith("generated_"):
        prompt_key = kind.replace("generated_", "", 1)
        return studio_image_filename(sku, prompt_key)
    if kind.startswith("color_"):
        color_name = kind.replace("color_", "", 1)
        prompt_key = "studio_classic"
        if url_name and url_name.startswith("capa_produto_"):
            rest = url_name.replace("capa_produto_", "").replace(".png", "")
            if rest.endswith(f"_{color_name}"):
                prompt_key = rest[: -len(f"_{color_name}")]
        return color_variation_filename(sku, prompt_key, color_name)
    return f"{sku}_{original_path.name}"


def candidate_source_paths(product: Product, asset: dict, data_dir: Path) -> list[Path]:
    recorded = Path(str(asset.get("path") or ""))
    candidates: list[Path] = []
    if recorded:
        candidates.append(recorded)

    sku = str(product.metadata.get("sku") or "").strip()
    project_id = product.project_id
    name_folder = PROJECTS_DIR / project_id / safe_folder_name(product.name)
    kind = str(asset.get("kind") or "")
    public_name = filename_from_public_url(asset.get("public_url"))

    if public_name:
        candidates.append(name_folder / public_name)
        if sku:
            candidates.append(product_assets_dir(project_id, sku) / target_filename(sku, kind, Path(public_name), asset.get("public_url")))

    if kind == "cover_image":
        candidates.extend([name_folder / "capa_produto.jpg", name_folder / f"{sku}_capa_produto.jpg" if sku else name_folder])
    elif kind == "model_3mf":
        candidates.extend([name_folder / "model.3mf", name_folder / f"{sku}_model.3mf" if sku else name_folder])
    elif public_name:
        candidates.append(name_folder / public_name)

    asset_id = str(asset.get("id") or "")
    if asset_id:
        for backup_root in (data_dir / "restored_backups").glob("*"):
            backup_file = backup_root / "files" / "assets" / f"{asset_id}{recorded.suffix if recorded.suffix else ''}"
            candidates.append(backup_file)
            for suffix in (".jpg", ".png", ".3mf", ".stl"):
                candidates.append(backup_root / "files" / "assets" / f"{asset_id}{suffix}")

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def resolve_source_path(product: Product, asset: dict, data_dir: Path) -> Path | None:
    for candidate in candidate_source_paths(product, asset, data_dir):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def already_in_sku_layout(product: Product, asset: dict) -> bool:
    sku = str(product.metadata.get("sku") or "").strip()
    if not sku:
        return False
    recorded = Path(str(asset.get("path") or ""))
    if not recorded:
        return False
    expected_parent = product_assets_dir(product.project_id, sku)
    expected_name = target_filename(sku, str(asset.get("kind") or ""), recorded, asset.get("public_url"))
    return recorded.parent == expected_parent and recorded.name == expected_name


def migrate(data_dir: Path | None = None) -> dict:
    data_dir = data_dir or DATA_DIR
    studio_path = data_dir / "studio.json"
    state = StudioState.model_validate(json.loads(studio_path.read_text(encoding="utf-8")))

    backup_path = data_dir / f"studio.pre_sku_layout_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy2(studio_path, backup_path)

    migrated_assets = 0
    missing_assets = 0
    skipped_assets = 0
    removed_dirs: list[str] = []

    for product in state.products:
        project = next((item for item in state.projects if item.id == product.project_id), None)
        store_profile = get_store_profile(project.store_profile_id if project else None)
        ensure_product_sku(product, state.products, project, store_profile)
        sku = str(product.metadata.get("sku") or "").strip().upper()
        product.metadata["sku"] = sku

        color_names = [asset.kind.replace("color_", "", 1) for asset in product.assets if asset.kind.startswith("color_")]
        if color_names:
            ensure_color_skus(product, color_names)

        target_dir = product_assets_dir(product.project_id, sku)
        target_dir.mkdir(parents=True, exist_ok=True)

        for asset in product.assets:
            asset_dict = asset.model_dump(mode="json")
            if already_in_sku_layout(product, asset_dict):
                skipped_assets += 1
                continue

            source = resolve_source_path(product, asset_dict, data_dir)
            if not source:
                missing_assets += 1
                continue

            destination = target_dir / target_filename(sku, asset.kind, source, asset.public_url)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.resolve() != destination.resolve():
                if destination.exists():
                    destination.unlink()
                shutil.copy2(source, destination)
            asset.path = str(destination)
            migrated_assets += 1

    store_path = studio_path
    store_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    legacy_dirs: set[Path] = set()
    for product in state.products:
        sku_folder = safe_sku_folder(str(product.metadata.get("sku") or ""))
        legacy = PROJECTS_DIR / product.project_id / safe_folder_name(product.name)
        if legacy.name != sku_folder:
            legacy_dirs.add(legacy)

    for legacy_dir in legacy_dirs:
        if not legacy_dir.exists() or not legacy_dir.is_dir():
            continue
        try:
            if not any(legacy_dir.iterdir()):
                legacy_dir.rmdir()
                removed_dirs.append(str(legacy_dir))
        except OSError:
            pass

    return {
        "backup": str(backup_path),
        "products": len(state.products),
        "migrated_assets": migrated_assets,
        "skipped_assets": skipped_assets,
        "missing_assets": missing_assets,
        "removed_empty_dirs": len(removed_dirs),
    }


def cleanup_legacy_folders(state: StudioState) -> dict[str, int]:
    removed = 0
    failed = 0
    for product in state.products:
        sku = str(product.metadata.get("sku") or "").strip()
        if not sku:
            continue
        legacy_dir = PROJECTS_DIR / product.project_id / safe_folder_name(product.name)
        sku_dir = product_assets_dir(product.project_id, sku)
        if not legacy_dir.exists() or legacy_dir.resolve() == sku_dir.resolve():
            continue
        if not sku_dir.exists():
            continue
        try:
            shutil.rmtree(legacy_dir)
            removed += 1
        except OSError:
            failed += 1
    return {"removed": removed, "failed": failed}


if __name__ == "__main__":
    summary = migrate()
    state = StudioState.model_validate(json.loads((DATA_DIR / "studio.json").read_text(encoding="utf-8")))
    summary["legacy_dirs"] = cleanup_legacy_folders(state)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
