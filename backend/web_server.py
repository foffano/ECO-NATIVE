import os
import shutil
from datetime import datetime, timezone

import uvicorn

from backend.app.core.paths import DB_PATH, EXPORTS_DIR


def preserve_pre_web_database() -> None:
    if not DB_PATH.exists():
        return
    backup_dir = EXPORTS_DIR / "pre_web_migration"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if any(backup_dir.glob("studio.pre_web_*.json")):
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    shutil.copy2(DB_PATH, backup_dir / f"studio.pre_web_{timestamp}.json")


def main(**server_options) -> None:
    preserve_pre_web_database()
    host = os.getenv("ECO_NATIVE_HOST", "127.0.0.1")
    port = int(os.getenv("ECO_NATIVE_PORT", "18765"))
    uvicorn.run("backend.app.main:app", host=host, port=port, log_level="info", **server_options)


if __name__ == "__main__":
    main()
