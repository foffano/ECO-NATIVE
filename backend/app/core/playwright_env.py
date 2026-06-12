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
        "chromium-*/chrome-linux/chrome",
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    )
    for pattern in patterns:
        matches = sorted(browsers_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def configure_playwright_browsers() -> Path | None:
    if os.getenv("PLAYWRIGHT_BROWSERS_PATH"):
        configured = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]).expanduser()
        return find_chromium_executable(configured)

    bundled = bundled_browsers_dir()
    executable = find_chromium_executable(bundled)
    if executable:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)
        return executable

    return None


def playwright_install_hint() -> str:
    return (
        "Chromium do Playwright não está instalado. "
        "No diretório do projeto, rode: npm run build:playwright"
    )
