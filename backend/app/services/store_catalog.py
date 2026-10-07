"""One catalog per store.

Products used to be grouped in projects inside a store, which only got in the
way. Each store now keeps exactly one internal project (its catalog); it is
never shown or chosen. `project_id` stays on records as the catalog id, so
file folders and stored paths keep working.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from backend.app.db.models import Project, StoreProfile, StudioState
from backend.app.db.store import store
from backend.app.services.authorization import store_project_ids
from backend.app.services.product_paths import product_assets_dir

logger = logging.getLogger(__name__)


def _new_catalog(profile: StoreProfile) -> Project:
    return Project(
        name=profile.name,
        store=profile.name,
        store_profile_id=profile.id,
        marketplace=profile.marketplace,
        niche=profile.niche,
    )


def store_catalog(state: StudioState, store_profile_id: str) -> Project | None:
    allowed = store_project_ids(state, store_profile_id)
    projects = [project for project in state.projects if project.id in allowed]
    return min(projects, key=lambda project: project.created_at) if projects else None


def ensure_store_catalog(store_profile_id: str) -> Project:
    """The store's catalog, created on first use."""
    existing = store_catalog(store.snapshot(), store_profile_id)
    if existing:
        return existing

    def apply(state: StudioState) -> Project:
        found = store_catalog(state, store_profile_id)
        if found:
            return found
        profile = next((item for item in state.store_profiles if item.id == store_profile_id), None)
        if profile is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Loja não encontrada")
        catalog = _new_catalog(profile)
        state.projects.append(catalog)
        return catalog

    return store.mutate(apply)


def _move_product_folder(old_project_id: str, new_project_id: str, sku: str) -> tuple[Path, Path] | None:
    """Moves a product's folder into the catalog; None leaves files in place."""
    if not sku:
        return None
    source = product_assets_dir(old_project_id, sku)
    target = product_assets_dir(new_project_id, sku)
    if not source.is_dir() or target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    return source, target


def unify_store_projects() -> int:
    """Merges every store's projects into a single catalog. Idempotent.

    The catalog is the project holding most products (the oldest on a tie).
    Moved products keep their files: each folder moves to the catalog and the
    stored paths follow; a folder that cannot move stays where it is, and its
    absolute paths remain valid. Returns how many products moved.
    """
    state = store.load()
    plans: list[tuple[StoreProfile, str, set[str]]] = []
    for profile in state.store_profiles:
        allowed = store_project_ids(state, profile.id)
        projects = [project for project in state.projects if project.id in allowed]
        if not projects or (len(projects) == 1 and projects[0].store_profile_id == profile.id):
            continue
        counts = {project.id: 0 for project in projects}
        for product in state.products:
            if product.project_id in counts:
                counts[product.project_id] += 1
        catalog = min(projects, key=lambda project: (-counts[project.id], project.created_at))
        plans.append((profile, catalog.id, {project.id for project in projects} - {catalog.id}))
    if not plans:
        return 0
    store.backup_snapshot("before-unify-projects")

    moved = 0
    for profile, catalog_id, others in plans:
        for product in [item for item in state.products if item.project_id in others]:
            sku = str(product.metadata.get("sku") or "").strip()
            moved_folder = _move_product_folder(product.project_id, catalog_id, sku)
            try:
                store.mutate(lambda current, product_id=product.id, folder=moved_folder, catalog_id=catalog_id:
                             _move_product_record(current, product_id, catalog_id, folder))
            except Exception:
                if moved_folder:
                    shutil.move(str(moved_folder[1]), str(moved_folder[0]))
                raise
            moved += 1
        store.mutate(lambda current, profile=profile, catalog_id=catalog_id, others=others:
                     _retire_projects(current, profile, catalog_id, others))
        logger.info("Store %s: merged %d project(s) into its catalog", profile.name, len(others))
    return moved


def _move_product_record(state: StudioState, product_id: str, catalog_id: str, folder: tuple[Path, Path] | None) -> None:
    index = next((i for i, item in enumerate(state.products) if item.id == product_id), None)
    if index is None:
        return
    product = state.products[index]
    if folder:
        # Paths appear in assets and in metadata (previous image versions).
        source, target = (_json_text(path) for path in folder)
        product = type(product).model_validate_json(product.model_dump_json().replace(source, target))
    product.project_id = catalog_id
    state.products[index] = product


def _json_text(path: Path) -> str:
    return str(path).replace("\\", "\\\\")


def _retire_projects(state: StudioState, profile: StoreProfile, catalog_id: str, others: set[str]) -> None:
    seen = {entry.url for entry in state.blocked_source_urls if entry.project_id == catalog_id}
    kept = []
    for entry in state.blocked_source_urls:
        if entry.project_id in others:
            if entry.url in seen:
                continue
            entry.project_id = catalog_id
            seen.add(entry.url)
        kept.append(entry)
    state.blocked_source_urls = kept
    for job in state.jobs:
        if job.project_id in others:
            job.project_id = catalog_id
    state.projects = [project for project in state.projects if project.id not in others]
    catalog = next(project for project in state.projects if project.id == catalog_id)
    catalog.store_profile_id = profile.id
    catalog.store = profile.name
