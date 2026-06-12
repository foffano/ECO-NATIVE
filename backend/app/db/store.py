import json
from pathlib import Path
from threading import Lock

from backend.app.core.paths import DB_PATH, ensure_app_dirs
from backend.app.db.models import AiProfile, Job, Product, Project, StoreProfile, StudioState, now_iso
from backend.app.services.product_status_migration import migrate_product_status_payload, migrate_product_statuses

_lock = Lock()


class JsonStore:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        ensure_app_dirs()
        if not self.path.exists():
            self.save(StudioState())

    def _load_unlocked(self) -> StudioState:
        if not self.path.exists():
            return StudioState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data, payload_changed = migrate_product_status_payload(data)
        state = StudioState.model_validate(data)
        model_changed = migrate_product_statuses(state)
        if payload_changed or model_changed:
            self.path.write_text(
                state.model_dump_json(),
                encoding="utf-8",
            )
        return state

    def _save_unlocked(self, state: StudioState) -> None:
        self.path.write_text(
            state.model_dump_json(),
            encoding="utf-8",
        )

    def load(self) -> StudioState:
        with _lock:
            return self._load_unlocked()

    def save(self, state: StudioState) -> None:
        with _lock:
            self._save_unlocked(state)

    def upsert_project(self, project: Project) -> Project:
        with _lock:
            state = self._load_unlocked()
            project.updated_at = now_iso()
            state.projects = [p for p in state.projects if p.id != project.id]
            state.projects.append(project)
            self._save_unlocked(state)
        return project

    def upsert_product(self, product: Product) -> Product:
        with _lock:
            state = self._load_unlocked()
            product.updated_at = now_iso()
            state.products = [p for p in state.products if p.id != product.id]
            state.products.append(product)
            self._save_unlocked(state)
        return product

    def upsert_job(self, job: Job) -> Job:
        with _lock:
            state = self._load_unlocked()
            job.updated_at = now_iso()
            state.jobs = [j for j in state.jobs if j.id != job.id]
            state.jobs.append(job)
            self._save_unlocked(state)
        return job

    def upsert_ai_profile(self, profile: AiProfile) -> AiProfile:
        with _lock:
            state = self._load_unlocked()
            profile.updated_at = now_iso()
            state.ai_profiles = [p for p in state.ai_profiles if p.id != profile.id]
            state.ai_profiles.append(profile)
            self._save_unlocked(state)
        return profile

    def upsert_store_profile(self, profile: StoreProfile) -> StoreProfile:
        with _lock:
            state = self._load_unlocked()
            profile.updated_at = now_iso()
            state.store_profiles = [p for p in state.store_profiles if p.id != profile.id]
            state.store_profiles.append(profile)
            self._save_unlocked(state)
        return profile


store = JsonStore()
