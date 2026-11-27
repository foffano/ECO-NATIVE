#!/usr/bin/env bash
# Builds "ECO Native Studio.app" for this Mac: API, interface and Chromium in one bundle.
#
#   scripts/build_macos_app.sh            # builds dist/macos/ECO Native Studio.app
#   scripts/build_macos_app.sh --install  # also copies it to /Applications
#
# PYTHON chooses the interpreter for the build environment (default python3.12).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_NAME="ECO Native Studio"
BUNDLE_ID="com.econative.studio"
VENV="$ROOT/.venv-macos"
OUT="$ROOT/dist/macos"
WORK="$ROOT/dist/macos-work"
APP="$OUT/$APP_NAME.app"
PYTHON="${PYTHON:-python3.12}"
INSTALL=false
[[ "${1:-}" == "--install" ]] && INSTALL=true

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Este script gera o app do macOS e precisa rodar num Mac." >&2
  exit 1
fi

step() { printf '\n==> %s\n' "$1"; }

pip_install() {
  if command -v uv >/dev/null 2>&1; then
    uv pip install --quiet --python "$VENV/bin/python" "$@"
  else
    "$VENV/bin/python" -m pip install --quiet "$@"
  fi
}

step "Ambiente Python ($VENV)"
if [[ ! -x "$VENV/bin/python" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --quiet --python "$PYTHON" "$VENV"
  else
    "$PYTHON" -m venv "$VENV"
  fi
fi
pip_install -r backend/requirements.txt -r backend/requirements-macos.txt

step "Interface"
[[ -d node_modules ]] || npm install --no-audit --no-fund
npm run build:frontend

step "Ícone"
mkdir -p "$WORK/icon.iconset"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" build/icon.png --out "$WORK/icon.iconset/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" build/icon.png --out "$WORK/icon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$WORK/icon.iconset" -o "$WORK/icon.icns"

step "App (PyInstaller)"
ECO_NATIVE_ICNS="$WORK/icon.icns" \
ECO_NATIVE_REVISION="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  "$VENV/bin/python" -m PyInstaller --noconfirm --clean \
    --distpath "$OUT" --workpath "$WORK/pyinstaller" \
    packaging/macos/eco_native.spec

step "Chromium do Playwright"
# Kept between builds, so only the first build (or a Playwright upgrade) downloads it.
PLAYWRIGHT_BROWSERS_PATH="$WORK/playwright-browsers" "$VENV/bin/python" -m playwright install chromium
# ditto keeps the symbolic links inside Chromium's own app bundle.
ditto "$WORK/playwright-browsers" "$APP/Contents/Resources/playwright-browsers"

step "Assinatura local"
# Ad hoc signature for this Mac. Chromium keeps Google's signature inside the bundle.
codesign --force --sign - "$APP"
codesign --verify "$APP"

step "Teste do app"
"$APP/Contents/MacOS/$APP_NAME" --self-test

if $INSTALL; then
  step "Instalando em /Applications"
  TARGET="/Applications/$APP_NAME.app"
  if [[ -d "$TARGET" ]]; then
    existing="$(defaults read "$TARGET/Contents/Info" CFBundleIdentifier 2>/dev/null || true)"
    if [[ "$existing" != "$BUNDLE_ID" ]]; then
      echo "$TARGET existe e não é o ECO Native Studio; nada foi substituído." >&2
      exit 1
    fi
    if pgrep -f "$TARGET/Contents/MacOS/" >/dev/null; then
      echo "Feche o ECO Native Studio antes de instalar a nova versão." >&2
      exit 1
    fi
    rm -rf "$TARGET"
  fi
  ditto "$APP" "$TARGET"
  echo "Instalado: $TARGET"
else
  echo
  echo "Pronto: $APP"
fi
