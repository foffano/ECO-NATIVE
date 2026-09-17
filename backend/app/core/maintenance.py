from backend.app.core.paths import DATA_DIR


def maintenance_requested() -> bool:
    return (DATA_DIR / ".maintenance").exists()
