"""Offline operational backups and cross-platform data-directory migration."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZIP_DEFLATED, ZipFile

from backend.app.core.atomic_files import atomic_write_text
from backend.app.core.paths import DATA_DIR, DB_PATH
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
    if not DB_PATH.is_file():
        raise ValueError("studio.json não encontrado")
    original = DB_PATH.read_text(encoding="utf-8")
    payload = remap_paths(json.loads(original), old_root, DATA_DIR)
    backup = DATA_DIR / "studio.before-path-migration.json"
    if not backup.exists():
        atomic_write_text(backup, original)
    atomic_write_text(DB_PATH, json.dumps(payload, ensure_ascii=False))


def backup(destination: Path):
    destination = destination.resolve()
    if destination.is_relative_to(DATA_DIR):
        raise ValueError("Salve o backup fora do diretório de dados")
    if destination.exists():
        raise ValueError("O arquivo de destino já existe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "x", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"kind": "eco-operational", "version": 1, "data_dir": str(DATA_DIR)}))
        for path in DATA_DIR.rglob("*"):
            if path.is_symlink() or not path.is_file() or path.name in {".server.lock", ".maintenance", "SingletonLock", "SingletonCookie", "SingletonSocket"}:
                continue
            archive.write(path, "data/" + path.relative_to(DATA_DIR).as_posix())
        if ENV_PATH.is_file() and not ENV_PATH.is_relative_to(DATA_DIR):
            archive.write(ENV_PATH, "data/.env")


def restore(source: Path):
    if any(path.name != ".server.lock" for path in DATA_DIR.iterdir()):
        raise ValueError("Restaure em um diretório de dados vazio; preserve a instalação atual para rollback")
    with ZipFile(source) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("kind") != "eco-operational" or manifest.get("version") != 1:
            raise ValueError("Use um backup operacional gerado por backend.maintenance")
        if "data/studio.json" not in archive.namelist():
            raise ValueError("Backup sem studio.json")
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
