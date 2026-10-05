import json
import logging
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import TypeVar

from backend.app.core.paths import DB_PATH, EXPORTS_DIR, ensure_app_dirs
from backend.app.core.atomic_files import atomic_write_text
from backend.app.db.models import AiProfile, Asset, Job, Product, Project, StoreProfile, StudioState, now_iso
from backend.app.services.product_status_migration import migrate_product_status_payload, migrate_product_statuses

logger = logging.getLogger(__name__)

_lock = Lock()
T = TypeVar("T")

STORE_SNAPSHOTS_DIR = EXPORTS_DIR / "store_snapshots"
MAX_AUTO_SNAPSHOTS = 20


class JsonStore:
    """studio.json with a parsed in-memory copy.

    The cached state is shared: `snapshot()` hands it out without copying, so
    callers must treat it as read-only. `load()` and `mutate()` work on deep
    copies. The cache is dropped on every write and whenever the file's
    mtime/size changes, so edits made by other processes are still picked up.
    """

    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self._cache: StudioState | None = None
        self._cache_stat: tuple[int, int] | None = None
        self._asset_index: dict[str, tuple[Product, Asset]] | None = None
        ensure_app_dirs()

    def _file_stat(self) -> tuple[int, int] | None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def _read_disk_unlocked(self) -> StudioState:
        if not self.path.exists():
            return StudioState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data, payload_changed = migrate_product_status_payload(data)
        state = StudioState.model_validate(data)
        model_changed = migrate_product_statuses(state)
        if payload_changed or model_changed:
            self._write_unlocked(state)
        return state

    def _current_unlocked(self) -> StudioState:
        stat = self._file_stat()
        if self._cache is None or stat != self._cache_stat:
            state = self._read_disk_unlocked()
            self._cache = state
            self._cache_stat = self._file_stat()
            self._asset_index = None
        return self._cache

    def _load_unlocked(self) -> StudioState:
        return self._current_unlocked().model_copy(deep=True)

    def _product_count_on_disk(self) -> int:
        try:
            return len(self._current_unlocked().products)
        except (json.JSONDecodeError, OSError, ValueError):
            return 0

    def _snapshot_path(self, label: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return STORE_SNAPSHOTS_DIR / f"studio.{label}_{timestamp}.json"

    def _backup_current_unlocked(self, label: str = "auto") -> Path | None:
        if not self.path.exists():
            return None
        STORE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        destination = self._snapshot_path(label)
        shutil.copy2(self.path, destination)
        self._prune_auto_snapshots_unlocked()
        return destination

    def _prune_auto_snapshots_unlocked(self) -> None:
        snapshots = sorted(
            STORE_SNAPSHOTS_DIR.glob("studio.auto_*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in snapshots[MAX_AUTO_SNAPSHOTS:]:
            stale.unlink(missing_ok=True)

    def _merge_products(self, current: list[Product], incoming: list[Product]) -> list[Product]:
        merged = {product.id: product for product in current}
        merged.update({product.id: product for product in incoming})
        return list(merged.values())

    def _merge_jobs(self, current: list[Job], incoming: list[Job]) -> list[Job]:
        merged = {job.id: job for job in current}
        merged.update({job.id: job for job in incoming})
        return list(merged.values())

    def _write_unlocked(self, state: StudioState) -> None:
        # Callers may keep mutating the objects they saved, so the cache is
        # rebuilt from disk on the next read instead of adopting `state`.
        self._cache = None
        self._cache_stat = None
        self._asset_index = None
        atomic_write_text(self.path, state.model_dump_json())

    def _save_unlocked(
        self,
        state: StudioState,
        *,
        allow_product_shrink: bool = False,
        replace_all: bool = False,
    ) -> None:
        if replace_all:
            previous_count = self._product_count_on_disk()
            new_count = len(state.products)
            if new_count < previous_count:
                backup = self._backup_current_unlocked("before_replace")
                if backup:
                    logger.warning(
                        "Store replace reduziu produtos de %s para %s. Backup: %s",
                        previous_count,
                        new_count,
                        backup,
                    )
            self._write_unlocked(state)
            return

        previous_count = self._product_count_on_disk()
        if not allow_product_shrink:
            # Read-only use: the merge only picks objects, it never edits them.
            current = self._current_unlocked()
            state.products = self._merge_products(current.products, state.products)
            state.jobs = self._merge_jobs(current.jobs, state.jobs)
        elif previous_count > len(state.products):
            backup = self._backup_current_unlocked("before_shrink")
            if backup:
                logger.warning(
                    "Produtos reduzidos de %s para %s. Backup: %s",
                    previous_count,
                    len(state.products),
                    backup,
                )

        self._write_unlocked(state)

    def load(self) -> StudioState:
        with _lock:
            return self._load_unlocked()

    def snapshot(self) -> StudioState:
        """Shared cached state for read-only paths. Never mutate the result."""
        with _lock:
            return self._current_unlocked()

    def find_asset(self, asset_id: str) -> tuple[Product, Asset] | None:
        """Read-only lookup of an asset and its product in the cached state."""
        with _lock:
            state = self._current_unlocked()
            if self._asset_index is None:
                self._asset_index = {
                    asset.id: (product, asset) for product in state.products for asset in product.assets
                }
            return self._asset_index.get(asset_id)

    def mutate(
        self,
        fn: Callable[[StudioState], T],
        *,
        allow_product_shrink: bool = False,
    ) -> T:
        with _lock:
            state = self._load_unlocked()
            result = fn(state)
            self._save_unlocked(state, allow_product_shrink=allow_product_shrink)
            return result

    def save(self, state: StudioState, *, allow_product_shrink: bool = False) -> None:
        with _lock:
            self._save_unlocked(state, allow_product_shrink=allow_product_shrink)

    def replace(self, state: StudioState) -> None:
        with _lock:
            self._save_unlocked(state, replace_all=True)

    def upsert_project(self, project: Project) -> Project:
        def apply(state: StudioState) -> Project:
            project.updated_at = now_iso()
            state.projects = [p for p in state.projects if p.id != project.id]
            state.projects.append(project)
            return project

        return self.mutate(apply)

    def upsert_product(self, product: Product) -> Product:
        def apply(state: StudioState) -> Product:
            product.updated_at = now_iso()
            product.metadata.pop("file_warnings", None)
            state.products = [p for p in state.products if p.id != product.id]
            state.products.append(product)
            return product

        return self.mutate(apply)

    def upsert_job(self, job: Job) -> Job:
        def apply(state: StudioState) -> Job:
            job.updated_at = now_iso()
            state.jobs = [j for j in state.jobs if j.id != job.id]
            state.jobs.append(job)
            return job

        return self.mutate(apply)

    def upsert_ai_profile(self, profile: AiProfile) -> AiProfile:
        def apply(state: StudioState) -> AiProfile:
            profile.updated_at = now_iso()
            state.ai_profiles = [p for p in state.ai_profiles if p.id != profile.id]
            state.ai_profiles.append(profile)
            return profile

        return self.mutate(apply)

    def upsert_store_profile(self, profile: StoreProfile) -> StoreProfile:
        def apply(state: StudioState) -> StoreProfile:
            profile.updated_at = now_iso()
            state.store_profiles = [p for p in state.store_profiles if p.id != profile.id]
            state.store_profiles.append(profile)
            return profile

        return self.mutate(apply)


store = JsonStore()
