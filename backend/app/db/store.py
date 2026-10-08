import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.app.core.paths import DB_PATH, EXPORTS_DIR, LEGACY_JSON_PATH, ensure_app_dirs
from backend.app.core.atomic_files import atomic_write_text
from backend.app.db.models import (
    AiProfile,
    Asset,
    BlockedSourceUrl,
    FilamentSpool,
    Job,
    PendingCleanup,
    PrintScheduleTask,
    Printer3D,
    Product,
    ProductionSettings,
    Project,
    StoreProfile,
    StudioState,
    now_iso,
)
from backend.app.services.product_status_migration import migrate_product_status_payload

logger = logging.getLogger(__name__)

_lock = Lock()
T = TypeVar("T")

STORE_SNAPSHOTS_DIR = EXPORTS_DIR / "store_snapshots"
MAX_AUTO_SNAPSHOTS = 20
SCHEMA_VERSION = 1


def _column_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


@dataclass(frozen=True)
class Collection:
    """One StudioState list stored as a table.

    Each row keeps the full model as JSON in `data`; `columns` are copies of
    fields that queries filter or sort on, kept in sync on every write.
    """

    attr: str
    model: type[BaseModel]
    key: str = "id"
    columns: dict[str, Callable[[Any], Any]] = field(default_factory=dict)

    @property
    def table(self) -> str:
        return self.attr

    def key_of(self, item: BaseModel) -> str:
        return getattr(item, self.key)

    def column_values(self, item: BaseModel) -> list[Any]:
        return [_column_value(getter(item)) for getter in self.columns.values()]


def _attr(name: str) -> Callable[[Any], Any]:
    return lambda item: getattr(item, name)


COLLECTIONS: tuple[Collection, ...] = (
    Collection("projects", Project, columns={"store_profile_id": _attr("store_profile_id"), "created_at": _attr("created_at")}),
    Collection(
        "products",
        Product,
        columns={
            "project_id": _attr("project_id"),
            "status": _attr("status"),
            "sku": lambda product: product.metadata.get("sku") or None,
            "created_at": _attr("created_at"),
            "updated_at": _attr("updated_at"),
        },
    ),
    Collection(
        "jobs",
        Job,
        columns={
            "project_id": _attr("project_id"),
            "product_id": _attr("product_id"),
            "status": _attr("status"),
            "created_at": _attr("created_at"),
        },
    ),
    Collection("ai_profiles", AiProfile),
    Collection("store_profiles", StoreProfile),
    Collection("blocked_source_urls", BlockedSourceUrl, columns={"project_id": _attr("project_id")}),
    Collection("filament_spools", FilamentSpool, columns={"store_profile_id": _attr("store_profile_id")}),
    Collection("production_settings", ProductionSettings, key="store_profile_id"),
    Collection("printers_3d", Printer3D),
    Collection(
        "print_schedule_tasks",
        PrintScheduleTask,
        columns={"printer_id": _attr("printer_id"), "scheduled_date": _attr("scheduled_date")},
    ),
    Collection("pending_cleanups", PendingCleanup),
)
COLLECTIONS_BY_MODEL = {collection.model: collection for collection in COLLECTIONS}


def _schema_statements() -> list[str]:
    statements = ["CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"]
    for collection in COLLECTIONS:
        columns = "".join(f", {name} TEXT" for name in collection.columns)
        statements.append(
            f"CREATE TABLE IF NOT EXISTS {collection.table} "
            f"(id TEXT PRIMARY KEY, seq INTEGER NOT NULL{columns}, data TEXT NOT NULL)"
        )
        statements.append(f"CREATE INDEX IF NOT EXISTS {collection.table}_seq ON {collection.table} (seq)")
        for name in collection.columns:
            statements.append(f"CREATE INDEX IF NOT EXISTS {collection.table}_{name} ON {collection.table} ({name})")
    statements += [
        "CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, product_id TEXT NOT NULL, kind TEXT NOT NULL, path TEXT)",
        "CREATE INDEX IF NOT EXISTS assets_product_id ON assets (product_id)",
    ]
    return statements


class StudioStore:
    """Studio data in SQLite, one row per record, with a parsed in-memory copy.

    The cached state is shared: `snapshot()` hands it out without copying, so
    callers must treat it as read-only. `load()` and `mutate()` work on deep
    copies, and writes only touch the rows that changed. The cache never holds
    objects a caller passed in, and it is reloaded when another connection
    (a maintenance command, a script) commits to the database.
    """

    def __init__(self, path: Path = DB_PATH, legacy_json_path: Path | None = LEGACY_JSON_PATH) -> None:
        self.path = path
        self.legacy_json_path = legacy_json_path
        self._conn: sqlite3.Connection | None = None
        self._cache: StudioState | None = None
        self._data_version: int | None = None
        self._asset_index: dict[str, tuple[Product, Asset]] | None = None
        ensure_app_dirs()

    # Connection and schema -------------------------------------------------

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            try:
                self._initialize(conn)
            except BaseException:
                conn.close()
                raise
            self._conn = conn
        return self._conn

    def _initialize(self, conn: sqlite3.Connection) -> None:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            # A release can add a collection; every statement is IF NOT EXISTS,
            # so this only creates the tables an older database lacks.
            conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in _schema_statements():
                    conn.execute(statement)
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            self._warn_if_legacy_json_changed(conn)
            return
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"{self.path} usa o esquema {version}; atualize o ECO Native para abri-lo")
        # Creating the schema and importing studio.json happen in one
        # transaction: a failed import leaves no half-migrated database behind.
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _schema_statements():
                conn.execute(statement)
            self._import_legacy_json(conn)
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise

    def _legacy_json_signature(self) -> str | None:
        if not self.legacy_json_path or not self.legacy_json_path.is_file():
            return None
        stat = self.legacy_json_path.stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"

    def _import_legacy_json(self, conn: sqlite3.Connection) -> None:
        signature = self._legacy_json_signature()
        if signature is None:
            return
        data = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
        data, _ = migrate_product_status_payload(data)
        state = StudioState.model_validate(data)
        for collection in COLLECTIONS:
            items = getattr(state, collection.attr)
            for seq, item in enumerate(items):
                self._write_row(conn, collection, item, seq)
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('legacy_json_signature', ?)", (signature,))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('legacy_json_imported_at', ?)", (now_iso(),))
        logger.info(
            "studio.json importado para %s: %s produtos, %s jobs",
            self.path,
            len(state.products),
            len(state.jobs),
        )

    def _warn_if_legacy_json_changed(self, conn: sqlite3.Connection) -> None:
        signature = self._legacy_json_signature()
        row = conn.execute("SELECT value FROM meta WHERE key = 'legacy_json_signature'").fetchone()
        if signature and row and row[0] != signature:
            logger.warning(
                "%s mudou depois da migracao para %s (uma versao antiga rodou?). "
                "Essas alteracoes nao aparecem no banco atual.",
                self.legacy_json_path,
                self.path,
            )

    def close(self) -> None:
        with _lock:
            if self._conn is not None:
                self._conn.close()
            self._conn = None
            self._cache = None
            self._asset_index = None

    # Rows ------------------------------------------------------------------

    def _write_row(self, conn: sqlite3.Connection, collection: Collection, item: BaseModel, seq: int | None) -> str:
        data = item.model_dump_json()
        names = list(collection.columns)
        values = collection.column_values(item)
        key = collection.key_of(item)
        if seq is None:
            # Existing row: keep its position.
            assignments = ", ".join(f"{name} = ?" for name in [*names, "data"])
            updated = conn.execute(
                f"UPDATE {collection.table} SET {assignments} WHERE id = ?",
                [*values, data, key],
            ).rowcount
            if not updated:
                seq = self._next_seq(conn, collection)
        if seq is not None:
            placeholders = ", ".join("?" for _ in range(len(names) + 3))
            updates = ", ".join(f"{name} = excluded.{name}" for name in [*names, "seq", "data"])
            conn.execute(
                f"INSERT INTO {collection.table} (id, seq, {''.join(name + ', ' for name in names)}data) "
                f"VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}",
                [key, seq, *values, data],
            )
        if collection.model is Product:
            self._write_assets(conn, item)
        return data

    @staticmethod
    def _write_assets(conn: sqlite3.Connection, product: Product) -> None:
        conn.execute("DELETE FROM assets WHERE product_id = ?", (product.id,))
        conn.executemany(
            "INSERT OR REPLACE INTO assets (id, product_id, kind, path) VALUES (?, ?, ?, ?)",
            [(asset.id, product.id, asset.kind, asset.path) for asset in product.assets],
        )

    @staticmethod
    def _delete_rows(conn: sqlite3.Connection, collection: Collection, keys: list[str]) -> None:
        conn.executemany(f"DELETE FROM {collection.table} WHERE id = ?", [(key,) for key in keys])
        if collection.model is Product:
            conn.executemany("DELETE FROM assets WHERE product_id = ?", [(key,) for key in keys])

    @staticmethod
    def _next_seq(conn: sqlite3.Connection, collection: Collection) -> int:
        return conn.execute(f"SELECT COALESCE(MAX(seq), -1) + 1 FROM {collection.table}").fetchone()[0]

    # Cache -----------------------------------------------------------------

    def _read_state_unlocked(self, conn: sqlite3.Connection) -> StudioState:
        values = {}
        for collection in COLLECTIONS:
            rows = conn.execute(f"SELECT data FROM {collection.table} ORDER BY seq").fetchall()
            values[collection.attr] = [collection.model.model_validate_json(row[0]) for row in rows]
        return StudioState(**values)

    def _current_unlocked(self) -> StudioState:
        conn = self._connection()
        data_version = conn.execute("PRAGMA data_version").fetchone()[0]
        if self._cache is None or data_version != self._data_version:
            self._cache = self._read_state_unlocked(conn)
            self._data_version = data_version
            self._asset_index = None
        return self._cache

    def _set_cache_unlocked(self, state: StudioState) -> None:
        self._cache = state
        self._data_version = self._connection().execute("PRAGMA data_version").fetchone()[0]
        self._asset_index = None

    # Writes ----------------------------------------------------------------

    def _commit_unlocked(self, before: StudioState, after: StudioState) -> None:
        """Write the rows that differ between two states, in one transaction."""
        conn = self._connection()
        cached: dict[str, list[BaseModel]] = {}
        conn.execute("BEGIN IMMEDIATE")
        try:
            for collection in COLLECTIONS:
                old_items = getattr(before, collection.attr)
                new_items = getattr(after, collection.attr)
                old_by_key = {collection.key_of(item): item for item in old_items}
                new_keys = [collection.key_of(item) for item in new_items]
                new_key_set = set(new_keys)

                removed = [key for key in old_by_key if key not in new_key_set]
                if removed:
                    self._delete_rows(conn, collection, removed)

                # Rows keep their seq unless the list was reordered; new rows
                # are appended. Anything else rewrites every position.
                appended = [key for key in new_keys if key not in old_by_key]
                reordered = new_keys != [key for key in old_by_key if key in new_key_set] + appended

                result: list[BaseModel] = []
                for index, item in enumerate(new_items):
                    key = new_keys[index]
                    previous = old_by_key.get(key)
                    if previous is not None and previous == item:
                        result.append(previous)
                        continue
                    data = self._write_row(conn, collection, item, None)
                    result.append(collection.model.model_validate_json(data))
                if reordered:
                    conn.executemany(
                        f"UPDATE {collection.table} SET seq = ? WHERE id = ?",
                        [(index, key) for index, key in enumerate(new_keys)],
                    )
                cached[collection.attr] = result
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            self._cache = None
            raise
        self._set_cache_unlocked(StudioState(**cached))

    def _snapshot_path(self, label: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        return STORE_SNAPSHOTS_DIR / f"studio.{label}_{timestamp}.json"

    def _backup_current_unlocked(self, label: str = "auto") -> Path | None:
        state = self._current_unlocked()
        STORE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        destination = self._snapshot_path(label)
        atomic_write_text(destination, state.model_dump_json())
        self._prune_auto_snapshots_unlocked()
        return destination

    def _prune_auto_snapshots_unlocked(self) -> None:
        snapshots = sorted(
            STORE_SNAPSHOTS_DIR.glob("studio.*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in snapshots[MAX_AUTO_SNAPSHOTS:]:
            stale.unlink(missing_ok=True)

    @staticmethod
    def _merge(current: list[BaseModel], incoming: list[BaseModel]) -> list[BaseModel]:
        merged = {item.id: item for item in current}
        merged.update({item.id: item for item in incoming})
        return list(merged.values())

    def _save_unlocked(
        self,
        state: StudioState,
        *,
        allow_product_shrink: bool = False,
        replace_all: bool = False,
    ) -> None:
        current = self._current_unlocked()
        if not replace_all and not allow_product_shrink:
            # Products and jobs are never dropped by accident: a stale state
            # saved over newer data only adds or updates them.
            state.products = self._merge(current.products, state.products)
            state.jobs = self._merge(current.jobs, state.jobs)
        elif len(state.products) < len(current.products):
            backup = self._backup_current_unlocked("before_replace" if replace_all else "before_shrink")
            logger.warning(
                "Produtos reduzidos de %s para %s. Backup: %s",
                len(current.products),
                len(state.products),
                backup,
            )
        self._commit_unlocked(current, state)

    def _upsert_unlocked(self, item: BaseModel) -> None:
        """Write one record and move it to the end of its list."""
        collection = COLLECTIONS_BY_MODEL[type(item)]
        current = self._current_unlocked()
        conn = self._connection()
        conn.execute("BEGIN IMMEDIATE")
        try:
            data = self._write_row(conn, collection, item, self._next_seq(conn, collection))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            self._cache = None
            raise
        key = collection.key_of(item)
        items = [existing for existing in getattr(current, collection.attr) if collection.key_of(existing) != key]
        items.append(collection.model.model_validate_json(data))
        self._set_cache_unlocked(current.model_copy(update={collection.attr: items}))

    # Public API ------------------------------------------------------------

    def load(self) -> StudioState:
        with _lock:
            return self._current_unlocked().model_copy(deep=True)

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
            state = self._current_unlocked().model_copy(deep=True)
            result = fn(state)
            self._save_unlocked(state, allow_product_shrink=allow_product_shrink)
            return result

    def save(self, state: StudioState, *, allow_product_shrink: bool = False) -> None:
        with _lock:
            self._save_unlocked(state.model_copy(), allow_product_shrink=allow_product_shrink)

    def replace(self, state: StudioState) -> None:
        with _lock:
            self._save_unlocked(state.model_copy(), replace_all=True)

    def export_json(self) -> str:
        with _lock:
            return self._current_unlocked().model_dump_json()

    def upsert_project(self, project: Project) -> Project:
        project.updated_at = now_iso()
        with _lock:
            self._upsert_unlocked(project)
        return project

    def upsert_product(self, product: Product) -> Product:
        product.updated_at = now_iso()
        product.metadata.pop("file_warnings", None)
        with _lock:
            self._upsert_unlocked(product)
        return product

    def backup_snapshot(self, label: str) -> Path | None:
        with _lock:
            return self._backup_current_unlocked(label)

    def merge_product_changes(self, base: Product, mine: Product) -> Product | None:
        """Write what a job changed from `base` to `mine` onto the stored product.

        Edits saved while the job ran are kept. A product deleted meanwhile
        stays deleted (returns None).
        """
        from backend.app.db.product_merge import merge_product

        with _lock:
            current = next((item for item in self._current_unlocked().products if item.id == mine.id), None)
            if current is None:
                return None
            merged = merge_product(base, mine, current.model_copy(deep=True))
            merged.updated_at = now_iso()
            merged.metadata.pop("file_warnings", None)
            self._upsert_unlocked(merged)
            return merged

    def upsert_job(self, job: Job) -> Job:
        job.updated_at = now_iso()
        with _lock:
            self._upsert_unlocked(job)
        return job

    def upsert_ai_profile(self, profile: AiProfile) -> AiProfile:
        profile.updated_at = now_iso()
        with _lock:
            self._upsert_unlocked(profile)
        return profile

    def upsert_store_profile(self, profile: StoreProfile) -> StoreProfile:
        profile.updated_at = now_iso()
        with _lock:
            self._upsert_unlocked(profile)
        return profile


store = StudioStore()
