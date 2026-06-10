from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from backend.app.core.paths import DATA_DIR, EXPORTS_DIR
from backend.app.db.models import AiProfile, Job, Product, Project, StoreProfile, StudioState, now_iso
from backend.app.db.store import store

BACKUP_VERSION = 1


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return cleaned.lower() or "loja"


def backup_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def add_file(
    archive: ZipFile,
    path_value: str | None,
    arcname: str,
    file_entries: list[dict],
    owner_type: str,
    owner_id: str,
    field: str,
) -> None:
    if not path_value:
        return
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return
    archive.write(path, arcname)
    file_entries.append(
        {
            "owner_type": owner_type,
            "owner_id": owner_id,
            "field": field,
            "arcname": arcname,
            "original_path": str(path),
        }
    )


def store_scope(state: StudioState, store_profile_id: str) -> tuple[StoreProfile, list[Project], list[Product], list[Job], list[AiProfile]]:
    profile = next((item for item in state.store_profiles if item.id == store_profile_id), None)
    if not profile:
        raise ValueError("Perfil de loja nao encontrado")

    projects = [
        project
        for project in state.projects
        if project.store_profile_id == profile.id or (not project.store_profile_id and project.store == profile.name)
    ]
    project_ids = {project.id for project in projects}
    products = [product for product in state.products if product.project_id in project_ids]
    product_ids = {product.id for product in products}
    jobs = [
        job
        for job in state.jobs
        if (job.project_id and job.project_id in project_ids) or (job.product_id and job.product_id in product_ids)
    ]
    ai_profiles = [item for item in state.ai_profiles if item.id == profile.ai_profile_id]
    return profile, projects, products, jobs, ai_profiles


def create_store_backup(store_profile_id: str) -> Path:
    state = store.load()
    profile, projects, products, jobs, ai_profiles = store_scope(state, store_profile_id)
    backups_dir = EXPORTS_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    output = backups_dir / f"backup-{slugify(profile.name)}-{backup_timestamp()}.zip"

    file_entries: list[dict] = []
    manifest = {
        "version": BACKUP_VERSION,
        "exported_at": now_iso(),
        "store_profile_id": profile.id,
        "store_profile_name": profile.name,
        "data": {
            "store_profiles": [profile.model_dump(mode="json")],
            "ai_profiles": [item.model_dump(mode="json") for item in ai_profiles],
            "projects": [item.model_dump(mode="json") for item in projects],
            "products": [item.model_dump(mode="json") for item in products],
            "jobs": [item.model_dump(mode="json") for item in jobs],
        },
        "files": file_entries,
    }

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        suffix = Path(profile.logo_path or "").suffix or ".img"
        add_file(archive, profile.logo_path, f"files/store_logo/{profile.id}{suffix}", file_entries, "store_profile", profile.id, "logo_path")

        for product in products:
            for asset in product.assets:
                suffix = Path(asset.path).suffix or ".asset"
                add_file(archive, asset.path, f"files/assets/{asset.id}{suffix}", file_entries, "asset", asset.id, "path")

        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return output


def backup_target_dir(store_profile_id: str) -> Path:
    path = DATA_DIR / "restored_backups" / f"{store_profile_id}_{backup_timestamp()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_backup_files(archive: ZipFile, manifest: dict) -> dict[tuple[str, str, str], str]:
    target_dir = backup_target_dir(str(manifest.get("store_profile_id") or "loja"))
    restored_paths: dict[tuple[str, str, str], str] = {}
    members = set(archive.namelist())

    for entry in manifest.get("files", []):
        arcname = str(entry.get("arcname") or "")
        if not arcname.startswith("files/") or arcname not in members:
            continue
        output = target_dir / arcname
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(archive.read(arcname))
        restored_paths[(str(entry.get("owner_type")), str(entry.get("owner_id")), str(entry.get("field")))] = str(output)

    return restored_paths


def upsert_many(existing: list, incoming: list, key: str = "id") -> list:
    incoming_ids = {getattr(item, key) for item in incoming}
    return [item for item in existing if getattr(item, key) not in incoming_ids] + incoming


def restore_store_backup(zip_bytes: bytes) -> dict:
    try:
        from io import BytesIO

        with ZipFile(BytesIO(zip_bytes)) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if int(manifest.get("version") or 0) != BACKUP_VERSION:
                raise ValueError("Versao de backup nao suportada")
            restored_paths = extract_backup_files(archive, manifest)
    except (BadZipFile, KeyError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Backup invalido ou incompatível") from exc

    data = manifest.get("data") or {}
    restored_profiles = [StoreProfile.model_validate(item) for item in data.get("store_profiles", [])]
    restored_ai_profiles = [AiProfile.model_validate(item) for item in data.get("ai_profiles", [])]
    restored_projects = [Project.model_validate(item) for item in data.get("projects", [])]
    restored_products = [Product.model_validate(item) for item in data.get("products", [])]
    restored_jobs = [Job.model_validate(item) for item in data.get("jobs", [])]

    for profile in restored_profiles:
        path = restored_paths.get(("store_profile", profile.id, "logo_path"))
        if path:
            profile.logo_path = path

    for product in restored_products:
        for asset in product.assets:
            path = restored_paths.get(("asset", asset.id, "path"))
            if path:
                asset.path = path

    state = store.load()
    state.store_profiles = upsert_many(state.store_profiles, restored_profiles)
    state.ai_profiles = upsert_many(state.ai_profiles, restored_ai_profiles)
    state.projects = upsert_many(state.projects, restored_projects)
    state.products = upsert_many(state.products, restored_products)
    state.jobs = upsert_many(state.jobs, restored_jobs)
    store.save(state)

    return {
        "store_profiles": len(restored_profiles),
        "ai_profiles": len(restored_ai_profiles),
        "projects": len(restored_projects),
        "products": len(restored_products),
        "jobs": len(restored_jobs),
        "files": len(restored_paths),
        "store_profile_id": manifest.get("store_profile_id"),
        "store_profile_name": manifest.get("store_profile_name"),
    }
