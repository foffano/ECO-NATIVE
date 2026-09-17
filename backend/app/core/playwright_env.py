import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def bundled_browsers_dir() -> Path:
    return project_root() / "dist" / "playwright-browsers"


def find_chromium_executable(browsers_dir: Path) -> Path | None:
    if not browsers_dir.is_dir():
        return None
    patterns = (
        "chromium-*/chrome-win64/chrome.exe",
        "chromium-*/chrome-linux64/chrome",
        "chromium-*/chrome-linux/chrome",
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        "chromium-*/chrome-mac-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    )
    for pattern in patterns:
        matches = sorted(browsers_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def configure_playwright_browsers(playwright=None) -> Path | None:
    if os.getenv("PLAYWRIGHT_BROWSERS_PATH"):
        configured = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]).expanduser()
        return find_chromium_executable(configured)

    bundled = bundled_browsers_dir()
    executable = find_chromium_executable(bundled)
    if executable:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)
        return executable
    # Let Playwright resolve its own default cache, including future layouts.
    if playwright is not None:
        executable = Path(playwright.chromium.executable_path)
    else:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as instance:
            executable = Path(instance.chromium.executable_path)
    if executable.is_file():
        return executable
    return None


def playwright_install_hint() -> str:
    return (
        "Chromium do Playwright não está instalado. "
        "Execute python -m playwright install --with-deps chromium no ambiente do servidor."
    )
