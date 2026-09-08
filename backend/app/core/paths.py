import os
from pathlib import Path

APP_NAME = "ECO Native Studio"


def get_data_dir() -> Path:
    override = os.getenv("ECO_NATIVE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    # Reuse the Electron production directory when migrating the installed app
    # to the web server. Electron used the lowercase package name on Windows.
    appdata = os.getenv("APPDATA")
    if appdata:
        appdata_path = Path(appdata)
        production_candidates = (
            appdata_path / "eco-native-studio",
            appdata_path / APP_NAME,
        )
        for candidate in production_candidates:
            if (candidate / "studio.json").exists():
                return candidate

    cwd = Path.cwd()
    if (cwd / "package.json").exists() and (cwd / "backend").exists():
        return cwd / "data"

    if appdata:
        return Path(appdata) / APP_NAME

    return Path.home() / ".eco-native-studio"


DATA_DIR = get_data_dir()
PROJECTS_DIR = DATA_DIR / "projects"
EXPORTS_DIR = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "studio.json"


def ensure_app_dirs() -> None:
    for path in (DATA_DIR, PROJECTS_DIR, EXPORTS_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
