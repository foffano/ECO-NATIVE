"""Importa o catálogo Toffa Decor de G:\\Meu Drive\\DFlow\\Lab\\Produtos para o ECO Native Studio."""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from backend.app.core.paths import DATA_DIR, PROJECTS_DIR  # noqa: E402
from backend.app.db.models import Asset, Product, ProductStatus, Project, StudioState, new_id, now_iso  # noqa: E402
from backend.app.services.product_paths import (  # noqa: E402
    color_variation_filename,
    cover_image_filename,
    model_filename,
    product_assets_dir,
    studio_image_filename,
)
from backend.app.services.sku import ensure_color_skus, ensure_product_sku  # noqa: E402
from backend.app.services.store_profiles import get_store_profile  # noqa: E402

SOURCE_ROOT = Path(r"G:\Meu Drive\DFlow\Lab\Produtos")
TOFFA_PROFILE_ID = "4d4767c45a934532bb69ace8e37ed524"
PROJECT_NAME = "Toffa Decor - Catálogo"

SKIP_DIR_NAMES = {"DESCONTINUADAS"}
SKIP_FILE_SUFFIXES = {".txt", ".mp4", ".mov", ".webm"}
SKIP_FILE_PATTERNS = (
    re.compile(r"_compressed(?:\.[^.]+)?$", re.I),
    re.compile(r"^Generated Image ", re.I),
    re.compile(r"^analysis\.txt$", re.I),
)

STUDIO_PROMPT_KEYS = (
    "studio_classic",
    "studio_angle",
    "studio_pedestal",
    "studio_close_up",
    "studio_ad_layout",
    "studio_decor",
)

LEGACY_STUDIO_SUFFIX_MAP = {
    "studio": "studio_classic",
    "dynamic": "studio_angle",
    "lifestyle": "studio_decor",
    "macro": "studio_close_up",
    "pedestal": "studio_pedestal",
    "angle": "studio_angle",
    "close_up": "studio_close_up",
    "ad_layout": "studio_ad_layout",
    "decor": "studio_decor",
}

COLOR_NAME_PATTERN = re.compile(r"_(PLA_[A-Za-z0-9]+|Velvet_White)(?:\.(?:png|jpe?g))?$", re.I)


def should_skip_file(path: Path) -> bool:
    if path.suffix.lower() in SKIP_FILE_SUFFIXES:
        return True
    name = path.name
    return any(pattern.search(name) for pattern in SKIP_FILE_PATTERNS)


def clean_product_name(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw.strip())
    if cleaned.isupper() or cleaned.islower():
        return cleaned.title()
    return cleaned


def build_display_name(category: str, folder_name: str) -> str:
    product_name = clean_product_name(folder_name)
    category_short = clean_product_name(category)
    if product_name.lower() == category_short.lower():
        return product_name
    return f"{category_short} - {product_name}"


def normalize_category(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip())


def discover_products(source_root: Path) -> list[dict]:
    products: list[dict] = []
    seen_paths: set[str] = set()

    for category_dir in sorted(source_root.iterdir()):
        if not category_dir.is_dir():
            continue
        category = normalize_category(category_dir.name)
        for product_dir in sorted(category_dir.iterdir()):
            if not product_dir.is_dir() or product_dir.name in SKIP_DIR_NAMES:
                continue
            key = str(product_dir.resolve())
            if key in seen_paths:
                continue
            seen_paths.add(key)
            products.append(
                {
                    "category": category,
                    "folder_name": product_dir.name,
                    "display_name": build_display_name(category, product_dir.name),
                    "source_dir": product_dir,
                    "origin": "direct",
                }
            )

    return products


def studio_key_from_stem(stem: str) -> str | None:
    for prompt_key in STUDIO_PROMPT_KEYS:
        if stem.endswith(f"_{prompt_key}"):
            return prompt_key
    for legacy_suffix, prompt_key in LEGACY_STUDIO_SUFFIX_MAP.items():
        if stem.endswith(f"_{legacy_suffix}"):
            return prompt_key
    return None


def color_name_from_stem(stem: str) -> str | None:
    match = COLOR_NAME_PATTERN.search(stem)
    if not match:
        return None
    return match.group(1)


def is_base_cover_candidate(path: Path) -> bool:
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return False
    stem = path.stem
    if studio_key_from_stem(stem):
        return False
    if color_name_from_stem(stem):
        return False
    if re.search(r"_(dynamic|lifestyle|macro|studio|pedestal|angle|decor|close_up|ad_layout)(?:_|$)", stem, re.I):
        return False
    return True


def pick_cover_source(files: list[Path]) -> Path | None:
    images = [path for path in files if is_base_cover_candidate(path)]
    if not images:
        return None
    priority_names = ("1.png", "1.jpeg", "1.jpg")
    for name in priority_names:
        match = next((path for path in images if path.name.lower() == name), None)
        if match:
            return match
    images.sort(key=lambda path: (len(path.name), path.name.lower()))
    return images[0]


def save_cover_jpg(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        rgb.save(destination, format="JPEG", quality=92)


def copy_binary(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def import_product_files(product: Product, sku: str, source_dir: Path) -> tuple[list[Asset], dict]:
    assets: list[Asset] = []
    stats = {"cover": 0, "model": 0, "generated": 0, "color": 0, "skipped": 0}
    target_dir = product_assets_dir(product.project_id, sku)
    target_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        [path for path in source_dir.iterdir() if path.is_file() and not should_skip_file(path)],
        key=lambda path: path.name.lower(),
    )

    model_files = [path for path in files if path.suffix.lower() == ".3mf"]
    if model_files:
        model_source = model_files[0]
        model_dest = target_dir / model_filename(sku, model_source.suffix.lower())
        copy_binary(model_source, model_dest)
        assets.append(Asset(product_id=product.id, kind="model_3mf", path=str(model_dest)))
        stats["model"] += 1

    cover_source = pick_cover_source(files)
    if cover_source:
        cover_dest = target_dir / cover_image_filename(sku)
        save_cover_jpg(cover_source, cover_dest)
        assets.append(Asset(product_id=product.id, kind="cover_image", path=str(cover_dest)))
        stats["cover"] += 1

    generated_keys: set[str] = set()
    color_names: set[str] = set()

    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".3mf":
            continue
        if path == cover_source:
            continue
        if suffix not in {".png", ".jpg", ".jpeg"}:
            stats["skipped"] += 1
            continue

        stem = path.stem
        color_name = color_name_from_stem(stem)
        if color_name:
            prompt_key = "studio_classic"
            for candidate in STUDIO_PROMPT_KEYS:
                token = f"_{candidate}_"
                if token in stem:
                    prompt_key = candidate
                    break
            dest = target_dir / color_variation_filename(sku, prompt_key, color_name)
            copy_binary(path, dest)
            assets.append(Asset(product_id=product.id, kind=f"color_{color_name}", path=str(dest)))
            color_names.add(color_name)
            stats["color"] += 1
            continue

        prompt_key = studio_key_from_stem(stem)
        if prompt_key:
            if prompt_key in generated_keys:
                stats["skipped"] += 1
                continue
            dest = target_dir / studio_image_filename(sku, prompt_key)
            copy_binary(path, dest)
            assets.append(Asset(product_id=product.id, kind=f"generated_{prompt_key}", path=str(dest)))
            generated_keys.add(prompt_key)
            stats["generated"] += 1
            continue

        stats["skipped"] += 1

    if color_names:
        ensure_color_skus(product, sorted(color_names))

    return assets, stats


def infer_status(assets: list[Asset]) -> ProductStatus:
    kinds = {asset.kind for asset in assets}
    if "cover_image" in kinds and "model_3mf" in kinds:
        if any(kind.startswith("generated_") for kind in kinds):
            return ProductStatus.ready
        return ProductStatus.in_edit
    return ProductStatus.collected


def ensure_project(state: StudioState) -> Project:
    existing = next((project for project in state.projects if project.store_profile_id == TOFFA_PROFILE_ID), None)
    if existing:
        return existing

    store_profile = get_store_profile(TOFFA_PROFILE_ID)
    project = Project(
        name=PROJECT_NAME,
        store=store_profile.name,
        store_profile_id=TOFFA_PROFILE_ID,
        niche="Decoração e utilidades 3D",
    )
    state.projects.append(project)
    return project


def main() -> dict:
    if not SOURCE_ROOT.exists():
        raise SystemExit(f"Pasta de origem não encontrada: {SOURCE_ROOT}")

    studio_path = DATA_DIR / "studio.json"
    state = StudioState.model_validate(json.loads(studio_path.read_text(encoding="utf-8")))
    backup_path = DATA_DIR / f"studio.pre_toffa_import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy2(studio_path, backup_path)

    project = ensure_project(state)
    store_profile = get_store_profile(TOFFA_PROFILE_ID)
    existing_names = {product.name.lower() for product in state.products if product.project_id == project.id}

    discovered = discover_products(SOURCE_ROOT)
    report: list[dict] = []
    imported = 0
    skipped = 0

    for item in discovered:
        display_name = item["display_name"]
        if display_name.lower() in existing_names:
            skipped += 1
            report.append({**item, "status": "skipped_duplicate", "sku": None, "source_dir": str(item["source_dir"])})
            continue

        product = Product(
            project_id=project.id,
            name=display_name,
            tags=[item["category"], "importado_manual", "toffa_decor"],
            metadata={
                "source": "manual_import",
                "import_category": item["category"],
                "import_folder": item["folder_name"],
                "import_origin": item["origin"],
                "imported_at": now_iso(),
            },
        )

        ensure_product_sku(product, state.products, project, store_profile)
        sku = str(product.metadata["sku"]).upper()
        assets, stats = import_product_files(product, sku, item["source_dir"])
        product.assets = assets
        product.status = infer_status(assets)

        if "descontinuada" in item["folder_name"].lower():
            product.tags.append("descontinuado")

        state.products.append(product)
        existing_names.add(display_name.lower())
        imported += 1
        report.append(
            {
                "name": display_name,
                "category": item["category"],
                "sku": sku,
                "folder": item["folder_name"],
                "source_dir": str(item["source_dir"]),
                "target_dir": str(product_assets_dir(project.id, sku)),
                "status": product.status.value,
                "assets": stats,
            }
        )

    studio_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    summary = {
        "backup": str(backup_path),
        "project_id": project.id,
        "project_name": project.name,
        "store_profile": store_profile.name,
        "discovered": len(discovered),
        "imported": imported,
        "skipped_duplicates": skipped,
    }

    report_path = DATA_DIR / "imports" / f"toffa_import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"summary": summary, "products": report}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["report"] = str(report_path)
    return summary


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))
