import json
from pathlib import Path
from threading import Lock

from backend.app.core.paths import DB_PATH, ensure_app_dirs
from backend.app.db.models import AiProfile, Job, Product, Project, StoreProfile, StudioState, now_iso

_lock = Lock()


class JsonStore:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        ensure_app_dirs()
        if not self.path.exists():
            self.save(StudioState())

    def load(self) -> StudioState:
        with _lock:
            if not self.path.exists():
                return StudioState()
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return StudioState.model_validate(data)

    def save(self, state: StudioState) -> None:
        with _lock:
            self.path.write_text(
                state.model_dump_json(indent=2),
                encoding="utf-8",
            )

    def upsert_project(self, project: Project) -> Project:
        state = self.load()
        project.updated_at = now_iso()
        state.projects = [p for p in state.projects if p.id != project.id]
        state.projects.append(project)
        self.save(state)
        return project

    def upsert_product(self, product: Product) -> Product:
        state = self.load()
        product.updated_at = now_iso()
        state.products = [p for p in state.products if p.id != product.id]
        state.products.append(product)
        self.save(state)
        return product

    def upsert_job(self, job: Job) -> Job:
        state = self.load()
        job.updated_at = now_iso()
        state.jobs = [j for j in state.jobs if j.id != job.id]
        state.jobs.append(job)
        self.save(state)
        return job

    def upsert_ai_profile(self, profile: AiProfile) -> AiProfile:
        state = self.load()
        profile.updated_at = now_iso()
        state.ai_profiles = [p for p in state.ai_profiles if p.id != profile.id]
        state.ai_profiles.append(profile)
        self.save(state)
        return profile

    def upsert_store_profile(self, profile: StoreProfile) -> StoreProfile:
        state = self.load()
        profile.updated_at = now_iso()
        state.store_profiles = [p for p in state.store_profiles if p.id != profile.id]
        state.store_profiles.append(profile)
        self.save(state)
        return profile


store = JsonStore()
