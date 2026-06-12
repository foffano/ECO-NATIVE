import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.playwright_env import configure_playwright_browsers, find_chromium_executable, bundled_browsers_dir


def main() -> None:
    configured = configure_playwright_browsers()
    if configured:
        return

    bundled = bundled_browsers_dir()
    if find_chromium_executable(bundled):
        return

    print("Instalando Chromium do Playwright em dist/playwright-browsers...")
    subprocess.check_call(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "prepare_playwright.py")],
        cwd=PROJECT_ROOT,
    )


if __name__ == "__main__":
    main()
