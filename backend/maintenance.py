"""Offline operational backups and cross-platform data-directory migration."""
import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZIP_DEFLATED, ZipFile

from backend.app.core.atomic_files import atomic_write_text
from backend.app.core.paths import DATA_DIR, DB_PATH, LEGACY_JSON_PATH
from backend.app.core.server_lock import server_lock
from backend.app.core.settings import ENV_PATH


def remap_paths(value, old_root: str, new_root: Path):
    if isinstance(value, dict):
        return {key: remap_paths(item, old_root, new_root) for key, item in value.items()}
    if isinstance(value, list):
        return [remap_paths(item, old_root, new_root) for item in value]
    if isinstance(value, str):
        path_type = PureWindowsPath if "\\" in old_root or PureWindowsPath(old_root).drive else PurePosixPath
        try:
            relative = path_type(value).relative_to(path_type(old_root))
            if ".." not in relative.parts:
                return str(new_root.joinpath(*relative.parts))
        except ValueError:
            pass
    return value


def migrate(old_root: str):
    if not DB_PATH.is_file() and not LEGACY_JSON_PATH.is_file():
        raise ValueError("Banco de dados não encontrado")
    if DB_PATH.is_file():
        from backend.app.db.models import StudioState
        from backend.app.db.store import StudioStore

        studio = StudioStore(DB_PATH, legacy_json_path=None)
        try:
            original = studio.export_json()
            backup = DATA_DIR / "studio.before-path-migration.json"
            if not backup.exists():
                atomic_write_text(backup, original)
            payload = remap_paths(json.loads(original), old_root, DATA_DIR)
            studio.replace(StudioState.model_validate(payload))
        finally:
            studio.close()
    if LEGACY_JSON_PATH.is_file():
        # Kept in step so a rollback to a JSON-only release finds valid paths.
        original = LEGACY_JSON_PATH.read_text(encoding="utf-8")
        payload = remap_paths(json.loads(original), old_root, DATA_DIR)
        if not DB_PATH.is_file():
            backup = DATA_DIR / "studio.before-path-migration.json"
            if not backup.exists():
                atomic_write_text(backup, original)
        atomic_write_text(LEGACY_JSON_PATH, json.dumps(payload, ensure_ascii=False))


def _database_copy(directory: Path) -> Path:
    """Consistent copy of the SQLite database, including WAL contents."""
    descriptor, name = tempfile.mkstemp(prefix=".studio-backup-", suffix=".db", dir=directory)
    os.close(descriptor)
    source = sqlite3.connect(DB_PATH)
    target = sqlite3.connect(name)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return Path(name)


def backup(destination: Path):
    destination = destination.resolve()
    if destination.is_relative_to(DATA_DIR):
        raise ValueError("Salve o backup fora do diretório de dados")
    if destination.exists():
        raise ValueError("O arquivo de destino já existe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    database = DB_PATH.relative_to(DATA_DIR).as_posix()
    skipped_database_files = {database, database + "-wal", database + "-shm", database + "-journal"}
    with ZipFile(destination, "x", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"kind": "eco-operational", "version": 1, "data_dir": str(DATA_DIR)}))
        if DB_PATH.is_file():
            copy = _database_copy(destination.parent)
            try:
                archive.write(copy, "data/" + database)
            finally:
                copy.unlink(missing_ok=True)
        for path in DATA_DIR.rglob("*"):
            if path.is_symlink() or not path.is_file() or path.name in {".server.lock", ".maintenance", "SingletonLock", "SingletonCookie", "SingletonSocket"}:
                continue
            relative = path.relative_to(DATA_DIR).as_posix()
            if relative in skipped_database_files:
                continue
            archive.write(path, "data/" + relative)
        if ENV_PATH.is_file() and not ENV_PATH.is_relative_to(DATA_DIR):
            archive.write(ENV_PATH, "data/.env")


def restore(source: Path):
    if any(path.name != ".server.lock" for path in DATA_DIR.iterdir()):
        raise ValueError("Restaure em um diretório de dados vazio; preserve a instalação atual para rollback")
    with ZipFile(source) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("kind") != "eco-operational" or manifest.get("version") != 1:
            raise ValueError("Use um backup operacional gerado por backend.maintenance")
        names = archive.namelist()
        if "data/studio.db" not in names and "data/studio.json" not in names:
            raise ValueError("Backup sem banco de dados (studio.db ou studio.json)")
        members = []
        for entry in archive.infolist():
            if entry.filename == "manifest.json":
                continue
            path = PurePosixPath(entry.filename)
            if "\\" in entry.filename or path.is_absolute() or ".." in path.parts or path.parts[0] != "data":
                raise ValueError("Caminho inválido no backup")
            output = DATA_DIR.joinpath(*path.parts[1:])
            if not output.resolve().is_relative_to(DATA_DIR):
                raise ValueError("Caminho fora do diretório de dados")
            members.append((entry, output))
        # Validate all names before writing any file.
        for entry, output in members:
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as src, output.open("wb") as dst:
                    import shutil
                    shutil.copyfileobj(src, dst)
        migrate(manifest["data_dir"])


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup").add_argument("archive", type=Path)
    commands.add_parser("restore").add_argument("archive", type=Path)
    commands.add_parser("migrate-paths").add_argument("old_root")
    args = parser.parse_args()
    with server_lock():
        if args.command == "backup":
            backup(args.archive)
        elif args.command == "restore":
            restore(args.archive)
        else:
            migrate(args.old_root)
    print("Operação concluída.")


if __name__ == "__main__":
    main()
