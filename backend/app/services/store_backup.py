from __future__ import annotations

import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from backend.app.core.paths import DATA_DIR, EXPORTS_DIR, PROJECTS_DIR
from backend.app.core.settings import ENV_PATH
from backend.app.db.models import (
    AiProfile,
    Job,
    Product,
    Project,
    StoreProfile,
    StudioState,
    now_iso,
)
from backend.app.db.store import store
from backend.app.services.product_paths import safe_sku_folder

BACKUP_VERSION_STORE = 1
BACKUP_VERSION_FULL = 2
STORE_LOGOS_DIR = DATA_DIR / "store_logos"


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


def add_directory_to_archive(archive: ZipFile, source_dir: Path, arc_prefix: str) -> int:
    if not source_dir.exists():
        return 0
    count = 0
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir).as_posix()
        archive.write(path, f"{arc_prefix}/{relative}")
        count += 1
    return count


def state_counts(state: StudioState) -> dict[str, int]:
    return {
        "store_profiles": len(state.store_profiles),
        "ai_profiles": len(state.ai_profiles),
        "projects": len(state.projects),
        "products": len(state.products),
        "jobs": len(state.jobs),
        "blocked_source_urls": len(state.blocked_source_urls),
        "filament_spools": len(state.filament_spools),
        "production_settings": len(state.production_settings),
        "printers_3d": len(state.printers_3d),
        "print_schedule_tasks": len(state.print_schedule_tasks),
    }


def create_app_backup() -> Path:
    state = store.load()
    backups_dir = EXPORTS_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    output = backups_dir / f"eco-native-backup-{backup_timestamp()}.zip"

    manifest = {
        "version": BACKUP_VERSION_FULL,
        "kind": "full_app",
        "exported_at": now_iso(),
        "data_dir": str(DATA_DIR),
        "counts": state_counts(state),
    }

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("data/studio.json", state.model_dump_json(indent=2))
        if ENV_PATH.exists() and ENV_PATH.is_file():
            archive.write(ENV_PATH, "data/.env")
        project_files = add_directory_to_archive(archive, PROJECTS_DIR, "files/projects")
        logo_files = add_directory_to_archive(archive, STORE_LOGOS_DIR, "files/store_logos")
        manifest["files"] = {
            "projects": project_files,
            "store_logos": logo_files,
            "env": ENV_PATH.exists() and ENV_PATH.is_file(),
        }
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return output


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
    return create_app_backup()


def backup_target_dir(label: str) -> Path:
    path = DATA_DIR / "restored_backups" / f"{label}_{backup_timestamp()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_backup_files(archive: ZipFile, manifest: dict) -> dict[tuple[str, str, str], str]:
    target_dir = backup_target_dir(str(manifest.get("store_profile_id") or "legacy_store"))
    restored_paths: dict[tuple[str, str, str], str] = {}
    members = set(archive.namelist())

    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
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


def restore_directory_from_archive(archive: ZipFile, arc_prefix: str, target_dir: Path) -> int:
    prefix = arc_prefix.rstrip("/") + "/"
    count = 0
    for name in archive.namelist():
        if not name.startswith(prefix) or name.endswith("/"):
            continue
        relative = name[len(prefix):]
        destination = target_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read(name))
        count += 1
    return count


def replace_directory_from_archive(archive: ZipFile, arc_prefix: str, target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    return restore_directory_from_archive(archive, arc_prefix, target_dir)


def remap_restored_paths(state: StudioState) -> None:
    for profile in state.store_profiles:
        if not profile.logo_path:
            continue
        filename = Path(profile.logo_path).name
        candidate = STORE_LOGOS_DIR / filename
        if candidate.exists():
            profile.logo_path = str(candidate)

    for product in state.products:
        sku = str(product.metadata.get("sku") or product.id).strip()
        product_dir = PROJECTS_DIR / product.project_id / safe_sku_folder(sku)
        for asset in product.assets:
            if not asset.path:
                continue
            filename = Path(asset.path).name
            candidate = product_dir / filename
            if candidate.exists():
                asset.path = str(candidate)


def read_manifest(zip_bytes: bytes) -> tuple[ZipFile, dict]:
    buffer = BytesIO(zip_bytes)
    archive = ZipFile(buffer)
    try:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except KeyError as exc:
        archive.close()
        raise ValueError("Backup invalido ou incompatível") from exc
    return archive, manifest


def restore_app_backup(zip_bytes: bytes) -> dict:
    archive, manifest = read_manifest(zip_bytes)
    try:
        version = int(manifest.get("version") or 0)
        if version != BACKUP_VERSION_FULL or manifest.get("kind") != "full_app":
            raise ValueError("Versao de backup nao suportada")
        if "data/studio.json" not in archive.namelist():
            raise ValueError("Backup invalido ou incompatível")

        state = StudioState.model_validate(json.loads(archive.read("data/studio.json").decode("utf-8")))
        project_files = replace_directory_from_archive(archive, "files/projects", PROJECTS_DIR)
        logo_files = replace_directory_from_archive(archive, "files/store_logos", STORE_LOGOS_DIR)

        env_restored = False
        if "data/.env" in archive.namelist():
            ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
            ENV_PATH.write_bytes(archive.read("data/.env"))
            env_restored = True

        remap_restored_paths(state)
        store.save(state)
    except (BadZipFile, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ValueError) and "Versao" in str(exc):
            raise
        raise ValueError("Backup invalido ou incompatível") from exc
    finally:
        archive.close()

    counts = state_counts(state)
    return {
        **counts,
        "files": project_files + logo_files,
        "env_restored": env_restored,
        "kind": "full_app",
    }


def restore_store_backup(zip_bytes: bytes) -> dict:
    try:
        with ZipFile(BytesIO(zip_bytes)) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            version = int(manifest.get("version") or 0)
            if version == BACKUP_VERSION_FULL and manifest.get("kind") == "full_app":
                return restore_app_backup(zip_bytes)
            if version != BACKUP_VERSION_STORE:
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
        "kind": "legacy_store",
        "store_profiles": len(restored_profiles),
        "ai_profiles": len(restored_ai_profiles),
        "projects": len(restored_projects),
        "products": len(restored_products),
        "jobs": len(restored_jobs),
        "files": len(restored_paths),
        "store_profile_id": manifest.get("store_profile_id"),
        "store_profile_name": manifest.get("store_profile_name"),
    }


def restore_backup(zip_bytes: bytes) -> dict:
    with ZipFile(BytesIO(zip_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    version = int(manifest.get("version") or 0)
    if version == BACKUP_VERSION_FULL and manifest.get("kind") == "full_app":
        return restore_app_backup(zip_bytes)
    return restore_store_backup(zip_bytes)
