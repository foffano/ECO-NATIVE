import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    browsers_dir = project_root / "dist" / "playwright-browsers"
    browsers_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)

    subprocess.check_call(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        cwd=project_root,
        env=env,
    )


if __name__ == "__main__":
    main()
