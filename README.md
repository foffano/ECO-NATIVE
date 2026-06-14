# ECO Native Studio

Estúdio desktop para coletar produtos, gerar anúncios e imagens com IA, e exportar para marketplaces.

**Stack:** React · FastAPI · Electron

## Dev

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
npm install
npm run build:playwright
npm run dev
```

- Frontend: http://127.0.0.1:5173  
- Backend: http://127.0.0.1:8765/health  
- Electron: `npm run dev:desktop`

## Build

```powershell
npm run dist:win    # instalador em %USERPROFILE%\ECO-NATIVE-release
npm run dist:mac    # requer macOS
```

Releases: [GitHub Releases](https://github.com/foffano/ECO-NATIVE/releases). Auto-update em **Ajustes → Verificar atualizações**.

Publicar:

```powershell
$env:GH_TOKEN = "seu_token"
powershell -File scripts\publish_github_release.ps1 -Version "x.y.z"
```

## Dados

| Ambiente | Local |
|----------|--------|
| Dev | `data/` |
| Instalado | pasta do usuário (Electron) |

Chaves de API: **Ajustes → Integrações** ou `.env`.
