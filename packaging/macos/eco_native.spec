# PyInstaller recipe for "ECO Native Studio.app".
# Run scripts/build_macos_app.sh: it builds the interface first, then adds Chromium
# to Contents/Resources and signs the bundle again.
import json
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]
APP_NAME = "ECO Native Studio"
VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]

a = Analysis(
    [str(ROOT / "backend" / "desktop_app.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "dist" / "frontend"), "dist/frontend")],
    # Uvicorn loads its event loop and protocol modules by name.
    hiddenimports=collect_submodules("uvicorn"),
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)
app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=os.environ.get("ECO_NATIVE_ICNS"),
    bundle_identifier="com.econative.studio",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "ECONativeRevision": os.environ.get("ECO_NATIVE_REVISION", "unknown"),
        "LSApplicationCategoryType": "public.app-category.business",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    },
)
